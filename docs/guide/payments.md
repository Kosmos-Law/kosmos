# Taking payments

This page is for the attorney or office manager who collects money from
clients. It covers recording a payment you received, applying payments to
invoices, and letting clients pay online from a link in an email. You need
the Financial permission for everything here. Ask your administrator.

Preparing and sending an invoice is covered in [Invoicing](invoicing.md).
The client trust ledger is covered in [Trust accounting](trust.md).

## How a payment works

A payment belongs to one matter. As soon as it is recorded it lowers
**Balance Due** on the matter's **Ledger**. Separately, a payment is
applied to invoices of that matter: each application puts part of the
payment against one invoice. An invoice becomes **Paid** when payments and
credits cover all of it. The part of a payment that is not applied to any
invoice is its unapplied amount.

## Record a payment on an invoice

1. Click **Invoicing** in the sidebar, then **Invoices**, and click the
   invoice's number.
2. Click **+ Card** beside the invoice's status. The button is there
   while the invoice is **Sent** or **Deferred**. Use it for a check, a
   wire or any other payment that does not come from trust.
3. **Add Payment** opens, filled in for this invoice. Set **Payment
   method**. **Amount** starts as what the invoice still owes: change it
   if you received a different amount.
4. Click **Submit**.

You are on the **Payments** tab, and the new payment is in the list.
Kosmos has applied it to the invoice, up to what the invoice still owed.
The invoice is **Paid** if nothing is left owing.

| Field | Required | Notes |
|---|---|---|
| **Matter** | Yes | The matter the payment is recorded on. The list holds only the invoice's matter. |
| **Date** | Yes | The date you received the money. It starts as today. |
| **Payment method** | Yes | **Check**, **Card**, **ACH / eCheck**, **Trust** or **Wire**. It starts on **Card**. Choosing **Trust** also records a trust withdrawal: see [Pay an invoice from trust](#pay-an-invoice-from-trust). |
| **Amount** | Yes | In dollars, and more than zero. It starts as the amount still due on the invoice. |
| **Detail** | No | A note shown in the **Payments** list, such as a check number. It starts as "Invoice 12", with the invoice's own number. |

Good to know:

- If the amount is more than the invoice still owes, the rest stays on
  the payment as unapplied money.

## Record a payment that is not for one invoice

1. Click **Invoicing**, then **Payments**, then the plus button at the
   left of the toolbar. **Add Payment** opens.
2. Choose the **Matter**. The list has every matter that is **Open** or
   **Complete**.
3. Fill in **Date**, **Payment method**, **Amount** and **Detail**, and
   click **Submit**.

The payment is in the list with its whole amount under **Unapplied**. No
invoice is marked paid until you apply it.

## Pay an invoice from trust

On the invoice's page, click **+ Trust** in place of **+ Card**. **Add
Payment** opens with **Payment method** set to **Trust**. When you click
**Submit**, Kosmos records the payment, applies it to the invoice, and
records a withdrawal of the same amount on the client's trust ledger.
[Pay an invoice from trust](trust.md#pay-an-invoice-from-trust) has the
details and the cautions.

A payment whose method is **Trust** records that withdrawal wherever you
enter it: under **+ Trust**, under **+ Card**, or in **Add Payment** on
the **Payments** tab. A payment by any other method records none. The
withdrawal carries the payment's date and amount. It changes when you
edit the payment and is deleted when you delete the payment.

Kosmos refuses a trust payment in two cases:

- The amount is more than the client's trust balance, counting deposits
  and withdrawals that are not confirmed yet. The form says "The client
  holds $500.00 in trust, which is less than this payment.", with the
  client's own balance.
- The matter has no client. Kosmos says "This matter has no client, so
  there is no trust balance to pay from. Set the client on the matter
  first."

## Apply a payment to invoices

1. On the **Payments** tab, click the payment's number under **ID**, then
   **Apply**.
2. **Apply Payment** shows the matter, the payment's date and amount, and
   **Unapplied Amount**. Under them is each unpaid invoice of the same
   matter (**Sent** or **Deferred**, with something still owing), oldest
   first, with its **Amount Due**.
3. Type an amount in **Amount to Apply** beside each invoice this payment
   is for. You choose the invoices: Kosmos does not fill them in.
4. Click **Submit**.

The dialog closes. The payment's **Unapplied** figure goes down, and an
invoice with nothing left owing becomes **Paid**.

An amount can be less than the invoice owes (a part payment). It cannot be
more, and the amounts together cannot be more than **Unapplied Amount**:
**Submit** stays switched off until they fit. If the matter has no unpaid
invoice, the dialog says "No unpaid invoices found for this matter."

To undo or change an application, open **Apply** again. **Current
Applications** lists each invoice the payment is applied to, with
**Amount Applied**. Click the X at the end of a row and confirm. The
money goes back to the payment's unapplied amount, and an invoice that
was **Paid** goes back to **Sent** (or to **Deferred**, if it was
deferred when it was paid).

A payment holds one application for each invoice. A further amount for
an invoice already under **Current Applications** is added to that
application. To lower an application, remove it and apply the amount you
want.

Good to know:

- A payment also becomes unapplied when the invoice it paid is voided.

## The Payments tab

**Invoicing → Payments** lists every payment on every matter, newest
first, ten to a page. **Total Payments** under the list adds up every
payment that matches the current filter, not only the page shown.

| Column | What it shows |
|---|---|
| **ID** | The payment's number. Click it for **Edit**, **Apply** and **Delete**. |
| **Date** | The date of the payment. |
| **Matter** | The matter. Click it to open the matter's **Ledger**. |
| **Method** | Check, Card, ACH / eCheck, Trust or Wire. |
| **Detail** | Your note. A payment made online reads "Online payment" and the name of the payment processor. |
| **Amount** | The amount received. |
| **Unapplied** | The part not applied to any invoice. |

To narrow or reorder the list:

- Click **All**, **Applied** or **Unapplied**. A payment is unapplied
  while any part of it is not applied to an invoice.
- Click **Filter** to open **Filter Payments**: **Payment method**,
  **Matter**, **Application Status**, **Date** (from and to) and
  **Ordering**. Click **Apply**. **Restore Defaults** clears the filter.
- Click the sort button beside **Date**, **Matter**, **Method** or
  **Detail**. Click it again to reverse the order.

A payment has no status of its own. The one mark you will see is a
**Pending** badge in **Detail**: an online bank payment that the bank has
not cleared yet. The same badge appears beside the invoice in the
**Invoices** list, in the invoice's **History** tab and on the matter's
**Ledger**.

## Edit or delete a payment

Anyone with the Financial permission can edit or delete any payment.

1. On the **Payments** tab, click the payment's number under **ID**.
2. Click **Edit**, change the fields in **Edit Payment** and click
   **Submit**. Or click **Delete**, then **Delete** again in the
   confirmation.

The list and the matter's **Ledger** show the change. You can do the same
from the matter's **Ledger**: click the payment's description, such as
"Payment by Check". **Edit Payment** on an online payment also shows the
processor's **Transaction ID**.

Kosmos checks an edit against the payment's applications:

- **Amount** cannot go below what is applied to invoices. The form says
  "$400.00 of this payment is applied to invoices. Remove an application
  first to make it smaller.", with the payment's own figure.
- **Matter** cannot change while any of the payment is applied. The form
  says "This payment is applied to invoices on its matter. Remove the
  applications first to move it."
- **Amount** must be more than zero: "Enter an amount greater than
  zero."

Deleting removes the payment and its applications. The matter's
**Balance Due** goes up, a part-paid invoice shows more owing, and an
invoice that was **Paid** goes back to **Sent** (or **Deferred**, if it
was deferred when it was paid).

A payment by **Trust** keeps its trust withdrawal in step. Editing the
payment changes the withdrawal's date, amount and description to match
(and its client, if you move the payment to another client's matter),
and the new amount is checked against the client's trust balance.
Changing the method to **Trust** records a withdrawal, changing it to
another method deletes the withdrawal, and deleting the payment deletes
the withdrawal with it.

Good to know:

- Deleting only removes the record. It does not send money back to the
  client.

## Let clients pay online

!!! note

    Online payment works once the person who runs your Kosmos server has
    connected a payment processor: see
    [Online payments](../admin/integrations/payments.md). Until then,
    the invoice emails carry **View invoice** instead of **Pay now**, and
    the **Request Payment** and **Request Deposit** actions are not shown.

### What the client receives

Every invoice email, invoice reminder, payment request and request
reminder has a **Pay now** button. It opens a payment page on your Kosmos
site. The client does not sign in.

A link works for 90 days from the day its email was sent, unless your
administrator has set a different period. After that the page says "This
payment link has expired. Please contact us for a new one." Send the
invoice or the request again and the new email carries a fresh link.

### What the payment page shows

The page for an invoice shows your firm's logo or name, the invoice number
and date, **Client**, **Amount Due**, a link to download the invoice as a
PDF, the payment fields and a **Pay** button with the amount on it. The
client pays the whole amount due and cannot change it. Card and bank
details go straight to the processor. Kosmos never receives or keeps them.

If your processor takes bank payments through Kosmos, the client chooses
between **Bank (eCheck)** and **Card**, and the page starts on the bank
option. Otherwise the page takes cards only.

After paying, the client sees "Payment received. Thank you." For a bank
payment the page says "Payment successful. Bank (eCheck) payments take 1–2
business days to clear." If the payment is declined, the page shows the
reason, nothing is recorded, and the client can try again. Once the
invoice is paid, the link shows "This invoice is paid in full. Thank you."
For an invoice that is **Void** or **Uncollectible**, the link shows
"This invoice is no longer open for payment. Please contact us if you
have a question about it."

### What Kosmos records

Kosmos records the payment the moment the processor accepts it: on the
invoice's matter, dated today, with the method **Card** or **ACH /
eCheck**, applied to the invoice. The invoice becomes **Paid**. Kosmos
treats a card payment as final at that point. A bank payment is recorded
at once too, with a **Pending** badge that goes away when the bank clears
it.

### If online payment is not set up

Invoice emails and invoice reminders carry a **View invoice** button
instead of **Pay now**, and their text no longer offers to take payment.
The page it opens shows the amount due and the invoice download, with
"Online payment is not available. Please contact us to arrange payment."
Nothing can be paid there. Links sent before online payment was turned off
open the same page.

Payment requests and trust deposit requests cannot be sent:

- **Request Payment**, **Request Trust Deposit** and the **Trust** tab's
  **Request Deposit** are not shown.
- The **Requests** tab is shown only while there are requests from
  before. They can be canceled but not resent or reminded.
- A request form opened another way says "Online payments are not set up.
  Requests cannot be sent." and sends nothing.

## Request payment of a balance

A payment request is an email asking a client to pay toward a matter's
open balance: what is still owing on its sent invoices, deferred ones
left out.

1. Click **Invoicing**, then **Requests**, then the plus button, then
   **Request Payment**.
2. Choose the **Matter**. **To** fills in with the client's email and
   **Amount** with the open balance.
3. Lower **Amount** to ask for part of the balance. It cannot be more
   than the balance. Add **Cc (optional)** and **Message (optional)** if
   you want them.
4. Tick **Include statement link** or **Include invoice links** to put
   download links for the matter statement or the open invoices in the
   email.
5. Click **Create Request**.

Kosmos sends the email and says "Payment request sent to" with the
address. The request is in the list as **Sent**. If the email cannot be
sent, no request is created.

When the client pays, Kosmos records one payment on the matter, applies it
to the open invoices oldest first, and marks the request **Paid**. The
client is charged the amount you asked for, or the open balance at that
moment if that is lower.

| Column | What it shows |
|---|---|
| **ID** | The request's number. While the request is **Sent**, click it for **Cancel**. |
| **Sent** | The date the request was created. |
| **Account** | **Operating** for a payment request, **Trust** for a trust deposit request. |
| **Matter / Client** | The matter (opens its **Ledger**) or, for a trust request, the client (opens their trust ledger). |
| **Recipients** | The addresses in **To**. |
| **Status** | **Sent**, **Paid** or **Canceled**. A badge such as ×2 counts the emails sent. **Pending** marks a bank payment that has not cleared. |
| **Amount** | The amount requested. |
| The send button | While the request is **Sent**: **Resend Request** and **Send Reminder**. Each email carries a fresh link. |

| Status | What it means |
|---|---|
| **Sent** | Emailed and not yet paid. The link works. A paid request goes back to **Sent** if its payment or deposit is later returned. |
| **Paid** | The client paid through the link. |
| **Canceled** | You canceled it. The link now says "This payment request is no longer active." |

Click **All**, **Sent**, **Paid** or **Canceled** to show one status.
**Filter** opens **Filter Requests**: **Matter**, **Account**, **Status**
and **Date**.

Good to know:

- The payment page for a request always offers the matter statement and
  each open invoice as a PDF, whether or not you ticked the boxes. The
  statement is the matter's whole ledger.
- A request becomes **Paid** only when it is paid through its link. If
  the client pays another way, record the payment and cancel the request.

## Request a trust deposit

1. On the **Requests** tab, click the plus button, then **Request Trust
   Deposit**. On the **Trust** tab the same form is under the plus button
   as **Request Deposit**.
2. Choose the **Client** (current and pending clients are listed), check
   **To**, and enter the **Deposit amount**.
3. Click **Request Deposit**.

The request is in the **Requests** list with **Trust** under **Account**.
When the client pays, Kosmos records a deposit on the client's trust
ledger, described "Online trust deposit" with the processor's name. The
deposit is not confirmed yet, and the request becomes **Paid**.
[Online trust deposits](trust.md#online-trust-deposits) explains how the
deposit is confirmed.

If the form opens with a message beginning "Trust deposit requests cannot
be sent", nothing is sent: the processor is not set up to keep trust money
apart. Ask your administrator.

## Fees and bank accounts

- The client is charged exactly the amount on the payment page. Kosmos
  adds no surcharge, and it does not record what the processor charges
  your firm.
- Payments on invoices and payment requests go to the firm's operating
  account. Trust deposit requests go to the trust account.

## Failed, returned and refunded payments

| What happened | What Kosmos does | What you do |
|---|---|---|
| A card or bank payment is declined on the payment page. | Shows the client the reason. Nothing is recorded. | Nothing. |
| A bank payment that was accepted later fails or is returned. | Deletes the payment, sets its invoices back to **Sent**, and emails the people your administrator set up to get server alerts. A payment request it had paid goes back to **Sent**. | Follow up with the client. Use the request's send button to resend it or send a reminder, or cancel it. |
| An online trust deposit later fails or is returned. | Deletes the deposit if it was not confirmed, and sends the same email. A confirmed deposit is left in place, with a **Returned** badge beside it on the **Trust** tab's **History** and on the client's ledger. Either way the deposit request goes back to **Sent**. | Correct a **Returned** deposit yourself on the client's trust ledger: see [Online trust deposits](trust.md#online-trust-deposits). |
| You need to refund a client. | Nothing. Kosmos has no refund button, and a refund made at the processor changes nothing you can see in Kosmos. | Refund in the processor's own website. Then delete the payment: an invoice it had paid goes back to **Sent**. For a part refund, remove the payment's applications, lower its **Amount** and apply it again. |

## Receipts and notices

Kosmos does not email a receipt to the client, and it does not tell the
firm when an online payment arrives. The client sees the confirmation on
the payment page, and the payment appears on the **Payments** tab.
