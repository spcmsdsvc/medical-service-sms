"""Leave Request workflow registered against the application's shared services.

This module is intentionally additive. It keeps the large legacy app module
stable while using the same database, storage, approval, notification, and
email helpers as the other Field Operations workflows.
"""

import hashlib
import io
import json
import os
import secrets
import tempfile
import threading
from datetime import datetime, timedelta

from flask import jsonify, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import inspect, text, or_


LEAVE_TYPES = ('Vacation Leave', 'Sick Leave', 'Maternity Leave', 'Leave Without Pay')
EDITABLE_STATUSES = {'Draft', 'Form to Follow', 'Rejected'}
ACTIVE_CONFLICT_STATUSES = {'Submitted', 'Approved'}
MAX_ATTACHMENTS = 10


def register_leave_feature(ctx):
    app = ctx['app']
    db = ctx['db']
    User = ctx['User']
    Engineer = ctx['Engineer']
    Shift = ctx['Shift']
    ShiftEngineer = ctx['ShiftEngineer']
    ActivityLog = ctx['ActivityLog']
    get_manila_time = ctx['get_manila_time']
    get_manila_today = ctx['get_manila_today']
    clean_str = ctx['clean_str']
    clean_int = ctx['clean_int']
    get_user_signature_snapshot = ctx['get_user_signature_snapshot']
    approval_user_display_name = ctx['approval_user_display_name']
    approval_user_title_label = ctx['approval_user_title_label']
    get_assigned_approvers_for_requester = ctx['get_assigned_approvers_for_requester']
    can_user_approve_for_requester = ctx['can_user_approve_for_requester']
    create_system_notification = ctx['create_system_notification']
    create_system_notifications_for_users = ctx['create_system_notifications_for_users']
    record_universal_approval_audit = ctx['record_universal_approval_audit']
    managed_storage_write_bytes = ctx['managed_storage_write_bytes']
    managed_storage_read_path = ctx['managed_storage_read_path']
    managed_storage_release_path = ctx['managed_storage_release_path']
    managed_storage_delete = ctx['managed_storage_delete']
    reimbursement_prepare_receipt_upload_bytes = ctx['reimbursement_prepare_receipt_upload_bytes']
    get_active_email_recipients_by_group = ctx['get_active_email_recipients_by_group']
    get_email_template_value = ctx['get_email_template_value']
    render_email_template = ctx['render_email_template']
    send_email_with_attachments = ctx['send_email_with_attachments']
    STORAGE_PREFIX_LEAVE_REQUESTS = ctx['STORAGE_PREFIX_LEAVE_REQUESTS']
    basedir = ctx['basedir']

    class LeaveRequest(db.Model):
        __tablename__ = 'leave_request'

        id = db.Column(db.Integer, primary_key=True)
        request_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
        engineer_id = db.Column(db.Integer, db.ForeignKey('engineer.id'), nullable=False, index=True)
        application_date = db.Column(db.Date, nullable=False)
        leave_type = db.Column(db.String(40), nullable=False, index=True)
        start_date = db.Column(db.Date, nullable=False, index=True)
        end_date = db.Column(db.Date, nullable=False, index=True)
        weekday_count = db.Column(db.Integer, default=0, nullable=False)
        reason = db.Column(db.Text, nullable=True)
        emergency_form_to_follow = db.Column(db.Boolean, default=False, nullable=False, index=True)
        verbal_approval_notes = db.Column(db.Text, nullable=True)
        provisional_created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
        provisional_created_at = db.Column(db.DateTime, nullable=True)
        status = db.Column(db.String(30), default='Draft', nullable=False, index=True)
        requester_name_snapshot = db.Column(db.String(160), nullable=True)
        requester_signature_snapshot = db.Column(db.Text, nullable=True)
        requester_signature_layout = db.Column(db.String(60), nullable=True)
        requester_signed_at = db.Column(db.DateTime, nullable=True)
        submitted_at = db.Column(db.DateTime, nullable=True)
        approved_at = db.Column(db.DateTime, nullable=True)
        approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
        rejected_at = db.Column(db.DateTime, nullable=True)
        rejected_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
        approval_remarks = db.Column(db.Text, nullable=True)
        approval_action = db.Column(db.String(20), nullable=True)
        approval_name_snapshot = db.Column(db.String(160), nullable=True)
        approval_title_snapshot = db.Column(db.String(160), nullable=True)
        approval_signature_snapshot = db.Column(db.Text, nullable=True)
        approval_signature_layout = db.Column(db.String(60), nullable=True)
        approval_signed_at = db.Column(db.DateTime, nullable=True)
        hr_email_status = db.Column(db.String(30), nullable=True)
        hr_email_remarks = db.Column(db.Text, nullable=True)
        hr_email_sent_at = db.Column(db.DateTime, nullable=True)
        calendar_group_id = db.Column(db.String(80), nullable=True, index=True)
        created_at = db.Column(db.DateTime, default=get_manila_time, nullable=False)
        updated_at = db.Column(db.DateTime, default=get_manila_time, onupdate=get_manila_time, nullable=False)

        attachments = db.relationship(
            'LeaveRequestAttachment', backref='leave_request', lazy=True,
            cascade='all, delete-orphan', order_by='LeaveRequestAttachment.uploaded_at'
        )

    class LeaveRequestAttachment(db.Model):
        __tablename__ = 'leave_request_attachment'

        id = db.Column(db.Integer, primary_key=True)
        leave_request_id = db.Column(db.Integer, db.ForeignKey('leave_request.id'), nullable=False, index=True)
        original_filename = db.Column(db.String(255), nullable=False)
        stored_filename = db.Column(db.String(255), nullable=False, unique=True)
        content_type = db.Column(db.String(120), nullable=True)
        file_size = db.Column(db.Integer, default=0, nullable=False)
        content_sha256 = db.Column(db.String(64), nullable=True, index=True)
        uploaded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
        uploaded_at = db.Column(db.DateTime, default=get_manila_time, nullable=False)

    class LeaveRequestAudit(db.Model):
        __tablename__ = 'leave_request_audit'

        id = db.Column(db.Integer, primary_key=True)
        leave_request_id = db.Column(db.Integer, db.ForeignKey('leave_request.id'), nullable=False, index=True)
        action = db.Column(db.String(80), nullable=False, index=True)
        actor_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
        remarks = db.Column(db.Text, nullable=True)
        created_at = db.Column(db.DateTime, default=get_manila_time, nullable=False)

    ctx['LeaveRequest'] = LeaveRequest
    ctx['LeaveRequestAttachment'] = LeaveRequestAttachment
    ctx['LeaveRequestAudit'] = LeaveRequestAudit

    schema_ready = {'value': False}

    def ensure_schema():
        if schema_ready['value']:
            return
        db.create_all()
        inspector = inspect(db.engine)
        shift_columns = {column['name'] for column in inspector.get_columns('shift')}
        if 'leave_request_id' not in shift_columns:
            db.session.execute(text('ALTER TABLE shift ADD COLUMN leave_request_id INTEGER'))
            db.session.commit()
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_shift_leave_request_id ON shift (leave_request_id)'))
            db.session.commit()
        except Exception:
            db.session.rollback()
        schema_ready['value'] = True

    ctx['ensure_leave_request_tables'] = ensure_schema

    @app.before_request
    def ensure_leave_request_schema_before_request():
        ensure_schema()

    def upload_root():
        root = '/data/uploads/leave_requests' if os.environ.get('RAILWAY_ENVIRONMENT') else os.path.join(basedir, 'static', 'uploads', 'leave_requests')
        os.makedirs(root, exist_ok=True)
        return root

    ctx['leave_request_attachment_upload_root'] = upload_root

    def parse_date(value):
        raw = clean_str(value) or ''
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y'):
            try:
                return datetime.strptime(raw, fmt).date()
            except Exception:
                continue
        return None

    def weekdays(start_date, end_date):
        if not start_date or not end_date or end_date < start_date:
            return []
        result = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                result.append(current)
            current += timedelta(days=1)
        return result

    def requester_name(header):
        if clean_str(header.requester_name_snapshot):
            return clean_str(header.requester_name_snapshot)
        user = db.session.get(User, header.user_id)
        return approval_user_display_name(user) or clean_str(getattr(user, 'username', None)) or 'Employee'

    def requester_email(header):
        user = db.session.get(User, header.user_id)
        profile = getattr(user, 'engineer_profile', None) if user else None
        return (clean_str(getattr(profile, 'email', None)) or '').lower()

    def request_number(application_date):
        prefix = f"LR-{application_date.strftime('%Y%m%d')}-"
        existing = LeaveRequest.query.filter(LeaveRequest.request_no.like(f'{prefix}%')).all()
        used = set()
        for row in existing:
            try:
                used.add(int((row.request_no or '').rsplit('-', 1)[-1]))
            except Exception:
                pass
        sequence = 1
        while sequence in used:
            sequence += 1
        return f'{prefix}{sequence:02d}'

    def is_management_user(user=None):
        target = user or current_user
        role = (clean_str(getattr(target, 'role', None)) or '').lower()
        return role in {'superadmin', 'regional_admin', 'admin', 'scheduler', 'manager'} or bool(getattr(target, 'can_approve_requests', False))

    def can_manage(header, user=None):
        target = user or current_user
        return bool(target and getattr(target, 'is_authenticated', False) and (header.user_id == target.id or is_management_user(target)))

    def can_approve(header, user=None):
        target = user or current_user
        if not target or not getattr(target, 'is_authenticated', False):
            return False
        return can_user_approve_for_requester(target, header.user_id, 'leave_request') or (clean_str(getattr(target, 'role', None)) or '').lower() == 'superadmin'

    def editable(header):
        return header.status in EDITABLE_STATUSES

    def audit(header, action, remarks=''):
        db.session.add(LeaveRequestAudit(
            leave_request_id=header.id,
            action=action,
            actor_user_id=current_user.id if getattr(current_user, 'is_authenticated', False) else None,
            remarks=clean_str(remarks) or ''
        ))

    def attachment_dict(item):
        return {
            'id': item.id,
            'filename': item.original_filename,
            'content_type': item.content_type or '',
            'file_size': int(item.file_size or 0),
            'preview_url': url_for('preview_leave_request_attachment', attachment_id=item.id),
            'download_url': url_for('download_leave_request_attachment', attachment_id=item.id),
        }

    def to_dict(header, include_attachments=True, include_audit=False):
        approver = db.session.get(User, header.approved_by_id) if header.approved_by_id else None
        rejector = db.session.get(User, header.rejected_by_id) if header.rejected_by_id else None
        result = {
            'id': header.id,
            'request_no': header.request_no,
            'user_id': header.user_id,
            'engineer_id': header.engineer_id,
            'requester_name': requester_name(header),
            'application_date': header.application_date.isoformat(),
            'leave_type': header.leave_type,
            'start_date': header.start_date.isoformat(),
            'end_date': header.end_date.isoformat(),
            'date_range': header.start_date.strftime('%b %d, %Y') if header.start_date == header.end_date else f"{header.start_date.strftime('%b %d, %Y')} - {header.end_date.strftime('%b %d, %Y')}",
            'weekday_count': int(header.weekday_count or 0),
            'reason': header.reason or '',
            'emergency_form_to_follow': bool(header.emergency_form_to_follow),
            'verbal_approval_notes': header.verbal_approval_notes or '',
            'status': header.status,
            'editable': editable(header) and can_manage(header),
            'can_approve': can_approve(header),
            'submitted_at': header.submitted_at.isoformat() if header.submitted_at else '',
            'approved_at': header.approved_at.isoformat() if header.approved_at else '',
            'approved_by': approval_user_display_name(approver) if approver else (header.approval_name_snapshot or ''),
            'rejected_at': header.rejected_at.isoformat() if header.rejected_at else '',
            'rejected_by': approval_user_display_name(rejector) if rejector else '',
            'approval_remarks': header.approval_remarks or '',
            'hr_email_status': header.hr_email_status or '',
            'hr_email_remarks': header.hr_email_remarks or '',
            'preview_url': url_for('preview_leave_request_pdf', leave_id=header.id),
            'download_url': url_for('download_leave_request_pdf', leave_id=header.id),
            'attachment_count': len(header.attachments),
        }
        if include_attachments:
            result['attachments'] = [attachment_dict(item) for item in header.attachments]
        if include_audit:
            rows = LeaveRequestAudit.query.filter_by(leave_request_id=header.id).order_by(LeaveRequestAudit.created_at.asc()).all()
            result['audit_trail'] = [{'action': row.action, 'remarks': row.remarks or '', 'created_at': row.created_at.isoformat()} for row in rows]
        return result

    ctx['leave_request_to_dict'] = to_dict

    def assigned_shift_ids(engineer_id):
        linked = [row.shift_id for row in ShiftEngineer.query.filter_by(engineer_id=engineer_id).all()]
        direct = [row.id for row in Shift.query.filter(or_(Shift.engineer_id == engineer_id, Shift.override_engineer_id == engineer_id)).all()]
        return set(linked + direct)

    def conflicts(engineer_id, start_date, end_date, exclude_leave_id=None):
        dates = weekdays(start_date, end_date)
        if not dates:
            return {'blocking_schedules': [], 'overlapping_leave_requests': []}
        shift_ids = assigned_shift_ids(engineer_id)
        schedules = []
        if shift_ids:
            for shift in Shift.query.filter(Shift.id.in_(shift_ids)).filter(Shift.start_time >= datetime.combine(dates[0], datetime.min.time())).filter(Shift.start_time < datetime.combine(dates[-1] + timedelta(days=1), datetime.min.time())).all():
                if exclude_leave_id and clean_int(getattr(shift, 'leave_request_id', None)) == exclude_leave_id:
                    continue
                schedules.append({
                    'id': shift.id,
                    'date': shift.start_time.date().isoformat(),
                    'title': shift.title,
                    'time': f"{shift.start_time.strftime('%I:%M %p')} - {shift.end_time.strftime('%I:%M %p')}",
                })
        query = LeaveRequest.query.filter_by(engineer_id=engineer_id).filter(LeaveRequest.status.in_(ACTIVE_CONFLICT_STATUSES)).filter(LeaveRequest.start_date <= end_date).filter(LeaveRequest.end_date >= start_date)
        if exclude_leave_id:
            query = query.filter(LeaveRequest.id != exclude_leave_id)
        overlaps = [{'id': row.id, 'request_no': row.request_no, 'date_range': f'{row.start_date.isoformat()} to {row.end_date.isoformat()}', 'status': row.status} for row in query.all()]
        return {'blocking_schedules': schedules, 'overlapping_leave_requests': overlaps}

    def update_calendar(header, state):
        """Create or update the request-owned weekday blocks without duplicates."""
        group_id = header.calendar_group_id or f'leave-request-{header.id}'
        header.calendar_group_id = group_id
        expected_dates = set(weekdays(header.start_date, header.end_date))
        existing = {row.start_time.date(): row for row in Shift.query.filter_by(leave_request_id=header.id).all()}
        status_map = {
            'Form to Follow': 'Form to Follow',
            'Pending Approval': 'Pending Approval',
            'Approved': 'Approved',
            'Unapproved / Rejected': 'Unapproved / Rejected',
        }
        for leave_date in expected_dates:
            start_at = datetime.combine(leave_date, datetime.strptime('08:00', '%H:%M').time())
            end_at = datetime.combine(leave_date, datetime.strptime('17:00', '%H:%M').time())
            row = existing.get(leave_date)
            if not row:
                row = Shift(
                    title=header.leave_type,
                    start_time=start_at,
                    end_time=end_at,
                    engineer_id=header.engineer_id,
                    status=status_map.get(state, state),
                    group_id=group_id,
                    schedule_type='leave_request',
                    leave_request_id=header.id,
                    created_at=get_manila_time(),
                )
                db.session.add(row)
                db.session.flush()
                db.session.add(ShiftEngineer(shift_id=row.id, engineer_id=header.engineer_id))
            else:
                row.title = header.leave_type
                row.start_time = start_at
                row.end_time = end_at
                row.status = status_map.get(state, state)
                row.group_id = group_id
                row.schedule_type = 'leave_request'
            existing.pop(leave_date, None)
        for obsolete in existing.values():
            ShiftEngineer.query.filter_by(shift_id=obsolete.id).delete(synchronize_session=False)
            db.session.delete(obsolete)

    ctx['update_leave_request_calendar'] = update_calendar

    def apply_payload(header, payload):
        leave_type = clean_str(payload.get('leave_type')) or ''
        start_date = parse_date(payload.get('start_date'))
        end_date = parse_date(payload.get('end_date'))
        if leave_type not in LEAVE_TYPES:
            raise ValueError('Select a valid leave type.')
        if not start_date or not end_date or end_date < start_date:
            raise ValueError('Select a valid leave date range.')
        leave_days = weekdays(start_date, end_date)
        if not leave_days:
            raise ValueError('The selected range contains no weekdays.')
        emergency = bool(payload.get('emergency_form_to_follow'))
        if emergency and leave_type != 'Sick Leave':
            raise ValueError('Form to Follow is available only for Sick Leave.')
        header.leave_type = leave_type
        header.start_date = start_date
        header.end_date = end_date
        header.weekday_count = len(leave_days)
        header.reason = clean_str(payload.get('reason')) or ''
        header.emergency_form_to_follow = emergency
        header.verbal_approval_notes = clean_str(payload.get('verbal_approval_notes')) or ''
        header.updated_at = get_manila_time()

    def find_header(leave_id, require_manage=True):
        header = db.session.get(LeaveRequest, clean_int(leave_id))
        if not header:
            return None
        if require_manage and not can_manage(header):
            return None
        return header

    def data_url_bytes(value):
        import base64
        raw = clean_str(value) or ''
        if ',' not in raw:
            return None
        try:
            return base64.b64decode(raw.split(',', 1)[1])
        except Exception:
            return None

    def template_path():
        return os.path.join(basedir, 'forms', 'Leave Form.pdf')

    def fill_pdf(header):
        from pypdf import PdfReader, PdfWriter
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas

        reader = PdfReader(template_path())
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)
        page = writer.pages[0]
        values = {
            'Date': header.application_date.strftime('%m/%d/%Y'),
            'Name': requester_name(header),
            'From': header.start_date.strftime('%m/%d/%Y'),
            'to': header.end_date.strftime('%m/%d/%Y'),
            'Inclusive': str(header.weekday_count),
            'Textfield': (header.reason or '')[:120],
            'Textfield1': (header.reason or '')[120:260],
            'Textfield-0': '',
            'Textfield-1': header.approval_name_snapshot or '',
            'Reason': header.approval_remarks if header.status == 'Rejected' else '',
            'Vacation Leave': '/On' if header.leave_type == 'Vacation Leave' else '/Off',
            'Sick Leave': '/On' if header.leave_type == 'Sick Leave' else '/Off',
            'Maternity Leave': '/On' if header.leave_type == 'Maternity Leave' else '/Off',
            'Leave without Pay': '/On' if header.leave_type == 'Leave Without Pay' else '/Off',
            'Approved': '/On' if header.status == 'Approved' else '/Off',
            'Disapproved': '/On' if header.status == 'Rejected' else '/Off',
            'Beg Balance of Leave': '', 'Leave Applied': '', 'Period': '',
            'End Balance of Leave': '', 'Amount': '', 'Text1': '', 'Text2': '', 'Text3': '',
        }
        writer.update_page_form_field_values(page, values, auto_regenerate=False)

        overlay = io.BytesIO()
        c = canvas.Canvas(overlay, pagesize=(595.32, 841.92))
        for signature, x, y, width, height in (
            (header.requester_signature_snapshot, 390, 687, 88, 25),
            (header.approval_signature_snapshot if header.status == 'Approved' else '', 395, 514, 88, 25),
        ):
            image_bytes = data_url_bytes(signature)
            if image_bytes:
                try:
                    c.drawImage(ImageReader(io.BytesIO(image_bytes)), x, y, width=width, height=height, preserveAspectRatio=True, mask='auto')
                except Exception:
                    pass
        c.showPage()
        c.save()
        overlay.seek(0)
        overlay_page = PdfReader(overlay).pages[0]
        writer.pages[0].merge_page(overlay_page)
        writer.set_need_appearances_writer(True)
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    def attachment_path(item):
        return os.path.join(upload_root(), os.path.basename(item.stored_filename))

    def compiled_attachments_pdf(header):
        if not header.attachments:
            return None
        import fitz
        output = fitz.open()
        opened = []
        paths = []
        try:
            for item in header.attachments:
                path = managed_storage_read_path(STORAGE_PREFIX_LEAVE_REQUESTS, attachment_path(item))
                paths.append(path)
                if (item.content_type or '').lower() == 'application/pdf' or item.original_filename.lower().endswith('.pdf'):
                    document = fitz.open(path)
                else:
                    image = fitz.open(path)
                    pdf_bytes = image.convert_to_pdf()
                    image.close()
                    document = fitz.open('pdf', pdf_bytes)
                opened.append(document)
                output.insert_pdf(document)
            return output.tobytes(garbage=4, deflate=True)
        finally:
            for document in opened:
                document.close()
            output.close()
            for path in paths:
                managed_storage_release_path(path)

    def email_subject(header):
        template = get_email_template_value('leave_request_hr_subject')
        return render_email_template(template, {
            'request_no': header.request_no,
            'requester': requester_name(header),
            'leave_type': header.leave_type,
            'date_range': f'{header.start_date.isoformat()} to {header.end_date.isoformat()}',
            'weekday_count': header.weekday_count,
            'approved_by': header.approval_name_snapshot or '',
        })

    def send_hr_email_background(leave_id):
        def worker():
            with app.app_context():
                header = db.session.get(LeaveRequest, leave_id)
                if not header:
                    return
                to_emails = list(get_active_email_recipients_by_group('leave_request_hr'))
                configured_cc = list(get_active_email_recipients_by_group('leave_request_cc'))
                request_email = requester_email(header)
                to_emails = list(dict.fromkeys([email.lower() for email in to_emails if email]))
                cc_emails = list(dict.fromkeys([email.lower() for email in configured_cc + ([request_email] if request_email else []) if email and email.lower() not in to_emails]))
                if not to_emails:
                    header.hr_email_status = 'warning'
                    header.hr_email_remarks = 'No active Leave Request HR recipient is configured in Settings.'
                    db.session.commit()
                    return
                temp_paths = []
                try:
                    attachments = []
                    form_file = tempfile.NamedTemporaryFile(prefix='leave-form-', suffix='.pdf', delete=False)
                    form_file.write(fill_pdf(header))
                    form_file.close()
                    temp_paths.append(form_file.name)
                    attachments.append({'display_name': f'{header.request_no}.pdf', 'path': form_file.name})
                    supporting = compiled_attachments_pdf(header)
                    if supporting:
                        support_file = tempfile.NamedTemporaryFile(prefix='leave-support-', suffix='.pdf', delete=False)
                        support_file.write(supporting)
                        support_file.close()
                        temp_paths.append(support_file.name)
                        attachments.append({'display_name': f'{header.request_no}_Supporting_Documents.pdf', 'path': support_file.name})
                    sent, message = send_email_with_attachments(
                        to_emails,
                        email_subject(header),
                        f'Approved Leave Request {header.request_no} for {requester_name(header)} is attached.',
                        attachments=attachments,
                        cc_emails=cc_emails,
                    )
                    if sent:
                        header.hr_email_status = 'sent'
                        header.hr_email_remarks = f"Sent to {', '.join(to_emails)}" + (f"; CC: {', '.join(cc_emails)}" if cc_emails else '')
                        header.hr_email_sent_at = get_manila_time()
                    else:
                        header.hr_email_status = 'failed'
                        header.hr_email_remarks = message or 'Email provider rejected the handoff.'
                except Exception as exc:
                    header.hr_email_status = 'failed'
                    header.hr_email_remarks = str(exc)[:1000]
                finally:
                    for temp_path in temp_paths:
                        try:
                            os.remove(temp_path)
                        except OSError:
                            pass
                db.session.commit()
        threading.Thread(target=worker, daemon=True).start()

    ctx['send_leave_request_hr_email_async'] = send_hr_email_background

    @app.route('/leave_request')
    @login_required
    def leave_request_page():
        profile = getattr(current_user, 'engineer_profile', None)
        if not profile and not is_management_user():
            return render_template('leave_request.html', leave_profile_missing=True, leave_can_create_for_others=False, leave_engineers=[])
        engineers = []
        if is_management_user():
            engineers = [{'id': row.id, 'user_id': row.user_id, 'name': row.name, 'branch': row.branch or ''} for row in Engineer.query.order_by(Engineer.name.asc()).all()]
        return render_template(
            'leave_request.html',
            leave_profile_missing=not bool(profile),
            leave_can_create_for_others=is_management_user(),
            leave_engineers=engineers,
            leave_current_engineer_id=profile.id if profile else None,
        )

    @app.route('/api/leave-requests', methods=['GET'])
    @login_required
    def list_leave_requests():
        query = LeaveRequest.query
        if is_management_user() and request.args.get('scope') == 'all':
            pass
        else:
            query = query.filter_by(user_id=current_user.id)
        rows = query.order_by(LeaveRequest.updated_at.desc(), LeaveRequest.id.desc()).limit(300).all()
        return jsonify({'success': True, 'items': [to_dict(row, include_attachments=False) for row in rows]})

    @app.route('/get_accounting_leave_request_queue', methods=['GET'])
    @login_required
    def get_accounting_leave_request_queue():
        status_filter = (clean_str(request.args.get('status')) or 'all').lower()
        query = LeaveRequest.query.filter_by(user_id=current_user.id)
        if status_filter == 'pending':
            query = query.filter(LeaveRequest.status.in_(['Draft', 'Form to Follow', 'Rejected']))
        elif status_filter == 'processing':
            query = query.filter(LeaveRequest.status == 'Submitted')
        elif status_filter == 'paid':
            query = query.filter(LeaveRequest.status == 'Approved')
        rows = query.order_by(LeaveRequest.updated_at.desc(), LeaveRequest.id.desc()).limit(300).all()
        all_rows = LeaveRequest.query.filter_by(user_id=current_user.id).all()
        summary = {
            'pending': sum(row.status in {'Draft', 'Form to Follow', 'Rejected'} for row in all_rows),
            'processing': sum(row.status == 'Submitted' for row in all_rows),
            'paid': sum(row.status == 'Approved' for row in all_rows),
        }
        return jsonify({
            'success': True,
            'queue': 'leave_requests',
            'items': [to_dict(row, include_attachments=False) for row in rows],
            'count': len(rows),
            'summary': summary,
        })

    @app.route('/api/leave-requests/<int:leave_id>', methods=['GET'])
    @login_required
    def get_leave_request(leave_id):
        header = find_header(leave_id)
        if not header and (header := db.session.get(LeaveRequest, leave_id)) and not can_approve(header):
            header = None
        if not header:
            return jsonify({'success': False, 'error': 'Leave Request not found or inaccessible.'}), 404
        return jsonify({'success': True, 'leave_request': to_dict(header, include_attachments=True, include_audit=True)})

    @app.route('/api/leave-requests/save', methods=['POST'])
    @login_required
    def save_leave_request():
        payload = request.get_json(silent=True) or {}
        header = find_header(payload.get('id')) if clean_int(payload.get('id')) else None
        if header and not editable(header):
            return jsonify({'success': False, 'error': 'This Leave Request is locked.'}), 409
        if not header:
            target_engineer = getattr(current_user, 'engineer_profile', None)
            target_user = current_user
            requested_engineer_id = clean_int(payload.get('engineer_id'))
            if requested_engineer_id and requested_engineer_id != clean_int(getattr(target_engineer, 'id', None)):
                if not is_management_user():
                    return jsonify({'success': False, 'error': 'You cannot create leave for another employee.'}), 403
                target_engineer = db.session.get(Engineer, requested_engineer_id)
                target_user = db.session.get(User, target_engineer.user_id) if target_engineer and target_engineer.user_id else None
            if not target_engineer or not target_user:
                return jsonify({'success': False, 'error': 'The selected employee is not linked to a system account.'}), 400
            today = get_manila_today()
            header = LeaveRequest(
                request_no=request_number(today), user_id=target_user.id, engineer_id=target_engineer.id,
                application_date=today, leave_type='Sick Leave', start_date=today, end_date=today,
                weekday_count=1, status='Draft', requester_name_snapshot=target_engineer.name,
            )
            db.session.add(header)
            db.session.flush()
            audit(header, 'draft_created')
        try:
            apply_payload(header, payload)
            audit(header, 'draft_saved')
            db.session.add(ActivityLog(user=current_user.username, action=f'Leave Request Draft Saved: {header.request_no}'))
            db.session.commit()
            return jsonify({'success': True, 'message': 'Leave Request draft saved.', 'leave_request': to_dict(header)})
        except ValueError as exc:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(exc)}), 400
        except Exception as exc:
            db.session.rollback()
            print(f'[LeaveRequest] Save failed: {exc}', flush=True)
            return jsonify({'success': False, 'error': 'Unable to save Leave Request.'}), 500

    @app.route('/api/leave-requests/check-conflicts', methods=['POST'])
    @login_required
    def check_leave_request_conflicts():
        payload = request.get_json(silent=True) or {}
        header = find_header(payload.get('id')) if clean_int(payload.get('id')) else None
        engineer_id = header.engineer_id if header else clean_int(payload.get('engineer_id') or getattr(getattr(current_user, 'engineer_profile', None), 'id', None))
        start_date = parse_date(payload.get('start_date'))
        end_date = parse_date(payload.get('end_date'))
        if not engineer_id or not start_date or not end_date:
            return jsonify({'success': False, 'error': 'Employee and leave dates are required.'}), 400
        result = conflicts(engineer_id, start_date, end_date, header.id if header else None)
        result['success'] = True
        result['has_conflicts'] = bool(result['blocking_schedules'] or result['overlapping_leave_requests'])
        return jsonify(result)

    @app.route('/api/leave-requests/<int:leave_id>/form-to-follow', methods=['POST'])
    @login_required
    def mark_leave_form_to_follow(leave_id):
        header = find_header(leave_id)
        if not header or not editable(header):
            return jsonify({'success': False, 'error': 'Editable Leave Request not found.'}), 404
        if header.leave_type != 'Sick Leave':
            return jsonify({'success': False, 'error': 'Form to Follow is available only for Sick Leave.'}), 400
        result = conflicts(header.engineer_id, header.start_date, header.end_date, header.id)
        if result['blocking_schedules'] or result['overlapping_leave_requests']:
            return jsonify({'success': False, 'error': 'The requested dates conflict with an existing commitment.', **result}), 409
        header.emergency_form_to_follow = True
        header.status = 'Form to Follow'
        header.provisional_created_by_id = current_user.id
        header.provisional_created_at = get_manila_time()
        update_calendar(header, 'Form to Follow')
        audit(header, 'form_to_follow_created', header.verbal_approval_notes)
        create_system_notification(header.user_id, 'Sick Leave Form to Follow', f'{header.request_no} is recorded on the Calendar. Complete and submit the signed form.', module='leave_request', record_id=header.id, target_url=f'/leave_request?open={header.id}')
        db.session.add(ActivityLog(user=current_user.username, action=f'Leave Request Form to Follow: {header.request_no}'))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Form-to-Follow Sick Leave recorded on the Calendar.', 'leave_request': to_dict(header)})

    @app.route('/api/leave-requests/<int:leave_id>/submit', methods=['POST'])
    @login_required
    def submit_leave_request(leave_id):
        header = find_header(leave_id)
        if not header or not editable(header):
            return jsonify({'success': False, 'error': 'Editable Leave Request not found.'}), 404
        if not clean_str(header.reason):
            return jsonify({'success': False, 'error': 'Reason for leave is required.'}), 400
        signature = get_user_signature_snapshot(current_user)
        if header.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Only the employee can formally submit and sign this Leave Request.'}), 403
        if not signature:
            return jsonify({'success': False, 'error': 'Your saved signature is required. Add it in Settings before submitting.', 'requires_signature': True}), 400
        result = conflicts(header.engineer_id, header.start_date, header.end_date, header.id)
        if result['blocking_schedules'] or result['overlapping_leave_requests']:
            return jsonify({'success': False, 'error': 'Submission blocked by an existing Calendar commitment or active Leave Request.', **result}), 409
        approvers = get_assigned_approvers_for_requester(header.user_id, 'leave_request')
        if not approvers:
            return jsonify({'success': False, 'error': 'No Leave Request approver is assigned in Settings.'}), 400
        previous = header.status
        now = get_manila_time()
        header.status = 'Submitted'
        header.submitted_at = now
        header.requester_signature_snapshot = signature
        header.requester_signature_layout = 'signature_over_printed_name'
        header.requester_signed_at = now
        header.rejected_at = None
        header.rejected_by_id = None
        header.approval_remarks = None
        if header.emergency_form_to_follow:
            update_calendar(header, 'Pending Approval')
        audit(header, 'submitted')
        record_universal_approval_audit('leave_request', header.id, 'submitted', actor_user=current_user, status_from=previous, status_to='Submitted', remarks='Leave Request submitted for approval.', metadata={'request_no': header.request_no})
        create_system_notifications_for_users(approvers, 'Leave Request Awaiting Approval', f'{header.request_no} from {requester_name(header)} is awaiting approval.', module='leave_request', record_id=header.id, target_url=f'/approvals?module=leave_request&id={header.id}', exclude_user_ids=[header.user_id])
        db.session.add(ActivityLog(user=current_user.username, action=f'Leave Request Submitted: {header.request_no}'))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Leave Request submitted for approval.', 'leave_request': to_dict(header)})

    @app.route('/api/leave-requests/approval-items', methods=['GET'])
    @login_required
    def leave_request_approval_items():
        status = clean_str(request.args.get('status')) or 'Submitted'
        if (clean_str(getattr(current_user, 'role', None)) or '').lower() == 'superadmin':
            query = LeaveRequest.query
        else:
            requester_ids = ctx['get_requester_user_ids_for_approver'](current_user, 'leave_request')
            query = LeaveRequest.query.filter(LeaveRequest.user_id.in_(requester_ids or [-1]))
        if status.lower() != 'all':
            query = query.filter(db.func.lower(LeaveRequest.status) == status.lower())
        rows = query.order_by(LeaveRequest.updated_at.desc()).limit(300).all()
        return jsonify({'success': True, 'items': [to_dict(row, include_attachments=False) for row in rows]})

    @app.route('/api/leave-requests/<int:leave_id>/approve', methods=['POST'])
    @login_required
    def approve_leave_request(leave_id):
        header = db.session.get(LeaveRequest, leave_id)
        if not header or header.status != 'Submitted' or not can_approve(header):
            return jsonify({'success': False, 'error': 'Submitted Leave Request not found or inaccessible.'}), 404
        signature = get_user_signature_snapshot(current_user)
        if not signature:
            return jsonify({'success': False, 'error': 'Your saved signature is required before approval.', 'requires_signature': True}), 400
        result = conflicts(header.engineer_id, header.start_date, header.end_date, header.id)
        if result['blocking_schedules'] or result['overlapping_leave_requests']:
            return jsonify({'success': False, 'error': 'Approval blocked because a new Calendar conflict was found.', **result}), 409
        payload = request.get_json(silent=True) or {}
        now = get_manila_time()
        header.status = 'Approved'
        header.approved_at = now
        header.approved_by_id = current_user.id
        header.approval_remarks = clean_str(payload.get('remarks')) or ''
        header.approval_action = 'Approved'
        header.approval_name_snapshot = approval_user_display_name(current_user)
        header.approval_title_snapshot = approval_user_title_label(current_user)
        header.approval_signature_snapshot = signature
        header.approval_signature_layout = 'signature_over_printed_name'
        header.approval_signed_at = now
        update_calendar(header, 'Approved')
        audit(header, 'approved', header.approval_remarks)
        record_universal_approval_audit('leave_request', header.id, 'approved', actor_user=current_user, status_from='Submitted', status_to='Approved', remarks=header.approval_remarks, metadata={'request_no': header.request_no})
        create_system_notification(header.user_id, 'Leave Request Approved', f'{header.request_no} was approved and added to the Calendar.', module='leave_request', record_id=header.id, target_url=f'/leave_request?open={header.id}')
        db.session.add(ActivityLog(user=current_user.username, action=f'Leave Request Approved: {header.request_no}'))
        db.session.commit()
        send_hr_email_background(header.id)
        return jsonify({'success': True, 'message': 'Leave Request approved. The Calendar was updated and HR handoff was queued.', 'leave_request': to_dict(header)})

    @app.route('/api/leave-requests/<int:leave_id>/reject', methods=['POST'])
    @login_required
    def reject_leave_request(leave_id):
        header = db.session.get(LeaveRequest, leave_id)
        if not header or header.status != 'Submitted' or not can_approve(header):
            return jsonify({'success': False, 'error': 'Submitted Leave Request not found or inaccessible.'}), 404
        payload = request.get_json(silent=True) or {}
        remarks = clean_str(payload.get('remarks')) or ''
        if not remarks:
            return jsonify({'success': False, 'error': 'Rejection remarks are required.'}), 400
        header.status = 'Rejected'
        header.rejected_at = get_manila_time()
        header.rejected_by_id = current_user.id
        header.approval_remarks = remarks
        if header.emergency_form_to_follow:
            update_calendar(header, 'Unapproved / Rejected')
        audit(header, 'rejected', remarks)
        record_universal_approval_audit('leave_request', header.id, 'rejected', actor_user=current_user, status_from='Submitted', status_to='Rejected', remarks=remarks, metadata={'request_no': header.request_no})
        create_system_notification(header.user_id, 'Leave Request Rejected', f'{header.request_no} was rejected. Review the manager remarks and resubmit if needed.', module='leave_request', record_id=header.id, target_url=f'/leave_request?open={header.id}', metadata={'remarks': remarks})
        db.session.add(ActivityLog(user=current_user.username, action=f'Leave Request Rejected: {header.request_no}'))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Leave Request rejected and returned for correction.', 'leave_request': to_dict(header)})

    @app.route('/api/leave-requests/<int:leave_id>/resend-hr', methods=['POST'])
    @login_required
    def resend_leave_request_hr(leave_id):
        header = db.session.get(LeaveRequest, leave_id)
        if not header or header.status != 'Approved' or not (can_approve(header) or is_management_user()):
            return jsonify({'success': False, 'error': 'Approved Leave Request not found or inaccessible.'}), 404
        header.hr_email_status = 'queued'
        header.hr_email_remarks = 'Manual resend queued.'
        db.session.commit()
        send_hr_email_background(header.id)
        return jsonify({'success': True, 'message': 'HR handoff resend queued.'})

    @app.route('/preview_leave_request/<int:leave_id>')
    @login_required
    def preview_leave_request_pdf(leave_id):
        header = db.session.get(LeaveRequest, leave_id)
        if not header or not (can_manage(header) or can_approve(header)):
            return jsonify({'success': False, 'error': 'Leave Request not found or inaccessible.'}), 404
        return send_file(io.BytesIO(fill_pdf(header)), mimetype='application/pdf', download_name=f'{header.request_no}.pdf', as_attachment=False)

    @app.route('/download_leave_request/<int:leave_id>')
    @login_required
    def download_leave_request_pdf(leave_id):
        header = db.session.get(LeaveRequest, leave_id)
        if not header or not (can_manage(header) or can_approve(header)):
            return jsonify({'success': False, 'error': 'Leave Request not found or inaccessible.'}), 404
        return send_file(io.BytesIO(fill_pdf(header)), mimetype='application/pdf', download_name=f'{header.request_no}.pdf', as_attachment=True)

    @app.route('/api/leave-requests/<int:leave_id>/attachments', methods=['POST'])
    @login_required
    def upload_leave_request_attachments(leave_id):
        header = find_header(leave_id)
        if not header or not editable(header):
            return jsonify({'success': False, 'error': 'Attachments can be changed only while the request is editable.'}), 409
        files = request.files.getlist('files') or request.files.getlist('attachments')
        if not files:
            return jsonify({'success': False, 'error': 'Select at least one attachment.'}), 400
        if len(header.attachments) + len(files) > MAX_ATTACHMENTS:
            return jsonify({'success': False, 'error': f'Maximum {MAX_ATTACHMENTS} attachments per Leave Request.'}), 400
        written = []
        try:
            existing_hashes = {item.content_sha256 for item in header.attachments if item.content_sha256}
            added = []
            for uploaded in files:
                original = os.path.basename(clean_str(uploaded.filename) or 'attachment')
                file_bytes, stored_ext, content_type = reimbursement_prepare_receipt_upload_bytes(uploaded, original)
                checksum = hashlib.sha256(file_bytes).hexdigest()
                if checksum in existing_hashes:
                    continue
                stored = f'leave-{header.id}-{secrets.token_hex(10)}.{stored_ext}'
                target = os.path.join(upload_root(), stored)
                managed_storage_write_bytes(STORAGE_PREFIX_LEAVE_REQUESTS, target, file_bytes, original_filename=original, content_type=content_type)
                written.append(target)
                item = LeaveRequestAttachment(
                    leave_request_id=header.id, original_filename=original, stored_filename=stored,
                    content_type=content_type, file_size=len(file_bytes), content_sha256=checksum,
                    uploaded_by_id=current_user.id,
                )
                db.session.add(item)
                existing_hashes.add(checksum)
                added.append(item)
            audit(header, 'attachments_uploaded', f'{len(added)} file(s)')
            db.session.commit()
            return jsonify({'success': True, 'message': f'{len(added)} attachment(s) uploaded.', 'attachments': [attachment_dict(item) for item in header.attachments]})
        except ValueError as exc:
            db.session.rollback()
            for path in written:
                try:
                    managed_storage_delete(STORAGE_PREFIX_LEAVE_REQUESTS, path)
                except Exception:
                    pass
            return jsonify({'success': False, 'error': str(exc)}), 400
        except Exception as exc:
            db.session.rollback()
            for path in written:
                try:
                    managed_storage_delete(STORAGE_PREFIX_LEAVE_REQUESTS, path)
                except Exception:
                    pass
            print(f'[LeaveRequest] Attachment upload failed: {exc}', flush=True)
            return jsonify({'success': False, 'error': 'Unable to upload attachment.'}), 500

    def authorized_attachment(attachment_id):
        item = db.session.get(LeaveRequestAttachment, attachment_id)
        header = db.session.get(LeaveRequest, item.leave_request_id) if item else None
        if not item or not header or not (can_manage(header) or can_approve(header)):
            return None, None
        return item, header

    @app.route('/preview_leave_request_attachment/<int:attachment_id>')
    @login_required
    def preview_leave_request_attachment(attachment_id):
        item, _ = authorized_attachment(attachment_id)
        if not item:
            return jsonify({'success': False, 'error': 'Attachment not found.'}), 404
        path = managed_storage_read_path(STORAGE_PREFIX_LEAVE_REQUESTS, attachment_path(item))
        return send_file(path, mimetype=item.content_type or 'application/octet-stream', download_name=item.original_filename, as_attachment=False)

    @app.route('/download_leave_request_attachment/<int:attachment_id>')
    @login_required
    def download_leave_request_attachment(attachment_id):
        item, _ = authorized_attachment(attachment_id)
        if not item:
            return jsonify({'success': False, 'error': 'Attachment not found.'}), 404
        path = managed_storage_read_path(STORAGE_PREFIX_LEAVE_REQUESTS, attachment_path(item))
        return send_file(path, mimetype=item.content_type or 'application/octet-stream', download_name=item.original_filename, as_attachment=True)

    @app.route('/api/leave-requests/attachments/<int:attachment_id>', methods=['DELETE'])
    @login_required
    def delete_leave_request_attachment(attachment_id):
        item, header = authorized_attachment(attachment_id)
        if not item or not header or not editable(header) or not can_manage(header):
            return jsonify({'success': False, 'error': 'Attachment cannot be deleted.'}), 409
        path = attachment_path(item)
        db.session.delete(item)
        audit(header, 'attachment_deleted', item.original_filename)
        db.session.commit()
        warning = ''
        try:
            managed_storage_delete(STORAGE_PREFIX_LEAVE_REQUESTS, path)
        except Exception as exc:
            warning = f'Storage cleanup warning: {exc}'
        return jsonify({'success': True, 'message': 'Attachment deleted.', 'warning': warning, 'attachments': [attachment_dict(row) for row in header.attachments if row.id != attachment_id]})

    @app.route('/api/leave-requests/<int:leave_id>/attachments', methods=['DELETE'])
    @login_required
    def delete_all_leave_request_attachments(leave_id):
        header = find_header(leave_id)
        if not header or not editable(header):
            return jsonify({'success': False, 'error': 'Attachments cannot be deleted.'}), 409
        items = list(header.attachments)
        paths = [attachment_path(item) for item in items]
        for item in items:
            db.session.delete(item)
        audit(header, 'attachments_deleted_all', f'{len(items)} file(s)')
        db.session.commit()
        warnings = []
        for path in paths:
            try:
                managed_storage_delete(STORAGE_PREFIX_LEAVE_REQUESTS, path)
            except Exception as exc:
                warnings.append(str(exc))
        return jsonify({'success': True, 'deleted_count': len(items), 'warning': '; '.join(warnings), 'attachments': []})

    @app.route('/api/leave-requests/<int:leave_id>', methods=['DELETE'])
    @login_required
    def delete_leave_request_draft(leave_id):
        header = find_header(leave_id)
        if not header or not editable(header):
            return jsonify({'success': False, 'error': 'Only editable Leave Requests can be deleted.'}), 409
        paths = [attachment_path(item) for item in header.attachments]
        for shift in Shift.query.filter_by(leave_request_id=header.id).all():
            ShiftEngineer.query.filter_by(shift_id=shift.id).delete(synchronize_session=False)
            db.session.delete(shift)
        LeaveRequestAudit.query.filter_by(leave_request_id=header.id).delete(synchronize_session=False)
        db.session.delete(header)
        db.session.commit()
        for path in paths:
            try:
                managed_storage_delete(STORAGE_PREFIX_LEAVE_REQUESTS, path)
            except Exception:
                pass
        return jsonify({'success': True, 'message': 'Leave Request draft deleted.'})
