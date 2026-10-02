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
   method** and change **Amount** to what you received.
4. Click **Submit**.

You are on the **Payments** tab, and the new payment is in the list.
Kosmos has applied it to the invoice, up to what the invoice still owed.
The invoice is **Paid** if nothing is left owing.

| Field | Required | Notes |
|---|---|---|
| **Matter** | Yes | The matter the payment is recorded on. Leave it as the invoice's matter. |
| **Date** | Yes | The date you received the money. It starts as today. |
| **Payment method** | Yes | **Check**, **Card**, **ACH / eCheck**, **Trust** or **Wire**. It starts on **Card**. |
| **Amount** | Yes | In dollars. |
| **Detail** | No | A note shown in the **Payments** list, such as a check number. It starts as "Invoice 12", with the invoice's own number. |

Good to know:

- **Amount** starts as the invoice's full total, even when part of the
  invoice has already been paid. Change it to what you received.
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

Choosing **Trust** as the method anywhere else records the payment only.
Nothing is withdrawn from trust.

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
money goes back to the payment's unapplied amount.

Good to know:

- A payment can hold one application for each invoice. To change an
  amount, or to add to an invoice already under **Current
  Applications**, remove that application and apply the full amount.
- When you remove the only payment on a **Paid** invoice, the invoice
  stays **Paid** with nothing owing. Open the invoice, click its status
  and choose **Sent** to make it owing again.
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

Good to know:

- Editing does not touch the payment's applications. Kosmos does not
  check a lower **Amount** against what is already applied, and changing
  **Matter** leaves the payment applied to the old matter's invoices.
  Remove the applications first.
- Deleting removes the payment and its applications. The matter's
  **Balance Due** goes up, and a part-paid invoice shows more owing. An
  invoice that was **Paid** stays **Paid**: open it, click its status and
  choose **Sent**.
- Deleting only removes the record. It does not send money back to the
  client, and it does not undo a trust withdrawal.

## Let clients pay online

!!! note

    Online payment works once the person who runs your Kosmos server has
    connected a payment processor: see
    [Online payments](../admin/integrations/payments.md). Nothing inside
    Kosmos shows whether one is connected, so ask your administrator.

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

### What Kosmos records

Kosmos records the payment the moment the processor accepts it: on the
invoice's matter, dated today, with the method **Card** or **ACH /
eCheck**, applied to the invoice. The invoice becomes **Paid**. Kosmos
treats a card payment as final at that point. A bank payment is recorded
at once too, with a **Pending** badge that goes away when the bank clears
it.

### If online payment is not set up

The emails still carry **Pay now**. The page shows the amount due and the
invoice download, with "Online payment is not available. Please contact us
to arrange payment." Nothing can be paid there.

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
| **Sent** | Emailed and not yet paid. The link works. |
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
- If a bank payment is returned later, the request still shows **Paid**.
  Send a new request.

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
| A bank payment that was accepted later fails or is returned. | Deletes the payment, sets its invoices back to **Sent**, and emails the people your administrator set up to get server alerts. | Follow up with the client. |
| An online trust deposit later fails or is returned. | Deletes the deposit if it was not confirmed, and sends the same email. A confirmed deposit is left in place. | Remove a confirmed deposit yourself on the client's trust ledger. |
| You need to refund a client. | Nothing. Kosmos has no refund button, and a refund made at the processor changes nothing you can see in Kosmos. | Refund in the processor's own website. Then delete or reduce the payment and set the invoice back to **Sent**. |

## Receipts and notices

Kosmos does not email a receipt to the client, and it does not tell the
firm when an online payment arrives. The client sees the confirmation on
the payment page, and the payment appears on the **Payments** tab.
