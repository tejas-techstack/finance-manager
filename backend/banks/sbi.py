"""SBI statement layout (from the statement screenshot).

Columns:
    Date | Transaction Reference | Ref.No./Chq.No. | Credit | Debit | Balance

Note SBI lists Credit BEFORE Debit; column order doesn't matter here because
we map by header keyword, not position.
"""

from .base import BankConfig

CONFIG = BankConfig(
    name="SBI",
    prefixes=["sbi"],
    date_headers=["date"],
    description_headers=["transaction reference", "transaction", "particulars", "narration", "description"],
    debit_headers=["debit", "withdrawal"],
    credit_headers=["credit", "deposit"],
    balance_headers=["balance"],
    date_formats=["%d-%m-%y", "%d/%m/%y", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%b-%Y"],
)
