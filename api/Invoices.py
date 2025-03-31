from datetime import datetime, timedelta
from .models import db, Leases, Invoices
from flask import make_response, jsonify

def generate_monthly_invoices():
    """
    Generates invoices for all active leases whose invoice date matches today's date.
    Handles edge cases and avoids duplicate invoice number generation.
    """
    try:
        today = datetime.today().date()
        leases = Leases.query.options(db.joinedload(Leases.property)).all()

        for lease in leases:
            if not (lease.start_date.day == today.day and lease.start_date <= today <= lease.end_date):
                continue

            # Check if we need to generate an invoice for this month
            last_invoice = Invoices.query.filter_by(lease_id=lease.id).order_by(Invoices.invoice_date.desc()).first()

            # Skip if an invoice already exists for this period
            if last_invoice and last_invoice.invoice_date.year == today.year and last_invoice.invoice_date.month == today.month:
                continue

            # Prepare invoice data
            property_name = lease.property.property_name if lease.property else "Unknown Property"
            invoice = Invoices(
                amount=lease.rent_amount,
                invoice_date=today,
                due_date=today + timedelta(days=7),
                balance=lease.rent_amount,
                description=f"Monthly rent for {property_name}",
                property_id=lease.property_id,
                tenant_id=lease.tenant_id,
                lease_id=lease.id
            )

            db.session.add(invoice)

        db.session.commit()

        return make_response(jsonify(
            {
                "type" : "success",
                "message" : "Invoices generated successfully"
            }
        ))

    except Exception as e:
        db.session.rollback()
        return make_response(jsonify(
            {
                "type" : "error",
                "message" : f"Error generating invoices: {str(e)}"
            }
        ))
