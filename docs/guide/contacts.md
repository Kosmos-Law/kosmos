# Contacts

This page is for anyone at the firm who keeps the address book: attorneys,
paralegals and office staff. It covers how to find, add, edit and delete
contacts, file them in folders, and connect them to matters, to each other
and to Google Contacts. If you are new to Kosmos, read
[Getting started](getting-started.md) first.

## What a contact is

A contact is one person or organization the firm deals with: a client, an
opposing party, another lawyer, a court, a witness. You enter a contact
once and can then place it on any number of matters.

You do not mark a contact as a client. A contact is a client because a
matter names it in its **Client** field (see [Matters](matters.md)). The
badge beside the contact's name, and the lists under **Clients**, follow
from those matters and change on their own when a matter's client or
status changes.

| Badge | List under **Clients** | When |
|---|---|---|
| **Current Client** | **Current** | The contact is the client on at least one matter that is **Open** or **Complete**. |
| **Potential Client** | **Pending** | The contact has no **Open** or **Complete** matter but is the client on a **Pending** one. Or it is the client on no matter and was created from an intake. |
| **Former Client** | **Former** | The contact is the client on one or more matters, and all of them are **Closed**. |
| **Nonclient** | None | The contact is the client on no matter and was not created from an intake. |

Only the matter's **Client** field counts. Placing a contact on a matter's
**Contacts** tab, in any role, does not make it a client.

## The Contacts page

Click **Contacts** in the sidebar. The page has three parts.

- On the left, **Clients** lists **Pending**, **Current** and **Former**,
  and **Folders** lists the firm's folders by name, then **Unsorted**.
  Click one to choose what the middle list shows. Click the highlighted
  one again to go back to **Unsorted**.
- In the middle, **Contacts** lists the names in your choice, in name
  order. Click a name to open the contact.
- On the right is the contact you opened.

The page starts on **Unsorted** (the contacts in no folder), then keeps
your choice until you change it or sign out. The list has no search box,
sort options or pages. An empty list reads "No contacts selected." On a
phone, the round folder button at the bottom right opens **Clients** and
**Folders**.

To find a contact wherever it is filed, use **Search** in the sidebar. See
[Search](getting-started.md#search).

Good to know:

- There is no list of every contact. A contact in a folder is not under
  **Unsorted**, and a contact that is not a client is under no **Clients**
  list. Use **Search** when you do not know where a contact is filed.
- When you open a contact from **Search** or from a matter, the middle
  list changes to that contact's folder, or to **Unsorted** if it has
  none. If you were on a **Clients** list and the contact is a client, it
  changes to the contact's **Clients** list instead.

## Add a contact

1. Click **Contacts** in the sidebar, then the **+** button at the top of
   the **Contacts** list. **Add Contact** opens. (From anywhere else,
   press Space, then `n`, and choose **Contact**.)
2. Enter the **Name**.
3. Fill in the other fields that apply and click **Submit**.

The new contact's page opens on its **Details** tab, and the middle list
shows the folder you put it in, or **Unsorted**.

| Field | Required | Notes |
|---|---|---|
| **Folder** | No | One of the firm's folders. Leave it blank for **Unsorted**. It starts on the folder you were viewing. |
| **Name** | Yes | 2 to 50 characters. A person or an organization. The list sorts by this field exactly as typed. |
| **Company** | No | Fewer than 50 characters. |
| **Email** | No | A valid email address. Saved in lower case. |
| **Email 2** | No | A second email address. |
| **Address** | No | Up to 250 characters, on as many lines as you need. |
| **Phone 1**, **Phone 2**, **Phone 3** | No | A 10-digit US number, typed any way you like. Add an extension after "x" or "ext". |
| **For** | No | The kind of number, set under each phone: **Mobile** (the default), **Home**, **Work**, **Fax** or **Other**. |
| **Website** | No | A web address such as https://example.com. |
| **Notes** | No | Fewer than 250 characters. |

Good to know:

- Kosmos does not check for duplicates, and two contacts cannot be merged.
  Use **Search** before you add someone.
- Only US numbers are accepted. Any other number is refused with "Enter a
  valid 10-digit US phone number." Put it in **Notes** instead.

## The contact's page

Click a contact's name. Its page opens with the name and client badge at
the top. At the top right, the copy button copies all of the contact's
details (on the **Details** tab only), the cloud button copies the contact
to Google Contacts (described below; it is there only when the firm's
Google account is connected), and the pencil button opens **Edit
Contact**.

| Tab | What it shows |
|---|---|
| **Details** | The name, company and address, with a button to copy them and, when there is an address, buttons to open it in Google Maps or look it up on Zillow. Then each email address, each phone number with its kind and buttons to copy or call it, the website, the notes, and **Open Matters**. |
| **Trust** | **Confirmed Balance** (confirmed trust transactions only) and **Pending Balance** (every trust transaction, confirmed or not). **View Full Trust Ledger** opens the client's trust ledger. |
| **Intake** | Whether the contact was created from an intake. If it was, and you have the Intakes permission, **View Intake Details** opens the intake. |
| **All Matters** | Every matter the contact is on, with **Status**, **Matter** and **ID**: **Open** matters first, then **Pending**, then **Complete** and **Closed**. Click a name to open the matter. |
| **Related** | The contact's relationships with other contacts. |

**Trust** and **Intake** appear only for a contact with a client badge,
not for a **Nonclient**. You need the Financial permission to see
**Trust**. Ask your administrator. **Assign to Matter** and **Remove from
Matter** are at the foot of every tab except **Related**.

Good to know:

- **Open Matters** and **All Matters** include every matter that has the
  contact on its **Contacts** tab in any role. If you can see only
  assigned matters, they list only those. **ID** is the matter's client
  reference number, or the number Kosmos gave it if it has none.

### Record how two contacts are related

1. Open the contact, click **Related**, then **Add Relationship**.
2. Under "Elena Rivera is …", choose the **Relationship**, for example
   **Employee of**, and the other **Contact**. **Notes** is optional.
3. Click **Submit**.

The relationship appears on both contacts' **Related** tabs, each in its
own words: Elena Rivera's says **Employee of**, and her employer's says
**Employer of**. Click the relationship in a row for **Edit** and
**Delete**. An administrator maintains the list of relationships under
**Settings → Contacts**.

## Edit a contact

1. Open the contact and click the pencil button at the top right. **Edit
   Contact** opens with the same fields as **Add Contact**.
2. Make your changes and click **Submit**.

The page reloads and shows the new details.

## Delete a contact

1. Open **Edit Contact** and click **Delete**.
2. A **Confirm** dialog asks "Delete this contact? It is removed from
   every matter it is on, and this cannot be undone." Click **Delete**.

The **Contacts** page opens again. The contact is gone from the list, and
no contact is open on the right.

Kosmos refuses to delete a contact that is the client on a matter
(whatever the matter's status), has trust activity, or has been sent a
trust deposit request (the message calls these payment requests). It
keeps the contact and gives the reason, for example "Elena Rivera was not
deleted: this contact is the client on 1 matter and has trust activity."

Deleting is permanent. Deleted with the contact:

- its place on every matter's **Contacts** tab;
- its relationships on other contacts' **Related** tabs;
- its copy in Google Contacts, if it has one.

The intake a contact was created from is kept.

## Organize contacts in folders

A folder is a named set of contacts, shared by the whole firm. A contact
is in one folder or in none (**Unsorted**).

- **Create a folder.** Click the **+** button beside **Folders**. In **Add
  Folder**, enter the **Folder Name** (50 characters at most) and click
  **Submit**.
- **Rename a folder.** Click the menu button beside the folder, then
  **Edit**. Change **Folder Name** and click **Submit**.
- **Move a contact.** Open **Edit Contact**, choose another **Folder** (or
  the blank choice for **Unsorted**) and click **Submit**. Contacts move
  one at a time.
- **Delete a folder.** Click the menu button beside the folder, then
  **Delete**. **Delete Folder** opens. For an empty folder, click
  **Delete**. If the folder holds contacts, it says how many and offers
  two buttons. **Keep Contacts** deletes the folder and moves its contacts
  to **Unsorted**. **Delete Folder and Contacts** deletes the folder and,
  without asking again, the contacts in it, with everything listed under
  [Delete a contact](#delete-a-contact).

**Delete Folder and Contacts** never deletes a contact that Kosmos would
refuse to delete on its own: a client on a matter, or a contact with
trust activity or a trust deposit request. Those contacts move to
**Unsorted**, and Kosmos says how many, for example "Kept 2 contacts that
are clients or have trust activity. Find them under Unsorted."

## Put a contact on a matter

On a matter, each contact has a **Group** (the side or cluster it belongs
to) and a **Role** (what it is on that matter). This is usually done on
the matter's **Contacts** tab, where you can also change and remove
assignments: see [Contacts](matters.md#contacts) in Matters. You can also
do it from the contact's page:

1. Click **Assign to Matter**. **Assign Contact to Matter** opens.
2. Choose the **Matter** (only **Open** matters that you can open are
   offered), the **Group** and the **Role**, then click **Submit**.

The **All Matters** tab opens with the matter in it. To take the contact
off a matter, click **Remove from Matter**. **Remove Contact from Matter**
opens. Choose under **Matter** (each choice names a matter and the
contact's role on it) and click **Submit**. The contact itself is kept.

A contact can hold more than one role on a matter, but Kosmos does not
put it on a matter twice in the same group and role. It says, for
example, "Marcus Bell is already on Rivera v. Northside Logistics as
Witness in Third Parties."

A matter's client is set in **Edit Matter**, not here. **Role** does not
offer **Client**, and **Remove Contact from Matter** does not offer the
row that stands for the matter's own client. When that leaves nothing to
choose, it says "There is no matter to remove this contact from. A
matter's client is changed in Edit Matter."

Good to know:

- **Group** offers the firm-wide groups only. To use a group made for one
  matter, assign the contact on that matter's **Contacts** tab.

## Contacts created from an intake

On an intake, the menu button has **Add to contacts**. It opens **Add
Contact** with the intake's name, address, phone and email filled in.
Click **Submit** and the contact is created as a **Potential Client**,
listed under **Pending**. The intake's menu then offers **Open contact**.
You can do the same while opening a matter, with **Convert an intake…**
(see [Matters](matters.md#add-the-client-while-you-open-the-matter)).
Both need the Intakes permission. Intakes are described in
[Intakes](intakes.md).

## Copy a contact to Google Contacts

If an administrator has connected the firm's Google account (see
[Google integrations](../admin/integrations/google.md)), you can copy
contacts to it one at a time. The cloud button is shown only while that
account is connected.

1. Open the contact.
2. Click the cloud button at the top right, beside the pencil button.

Kosmos adds the contact to the firm's Google Contacts and reloads the
page. The button is now highlighted and shows a crossed-out cloud. Click
it again to remove the contact from Google Contacts.

Good to know:

- Nothing is copied until you click the button, and nothing comes back
  from Google. Google receives the **Name**, the first **Email** and the
  three phone numbers only.
- Each time you edit a copied contact, Kosmos replaces the copy in Google
  Contacts, so anything added to it in Google is lost.

## Who can see contacts

Every user can see, add, edit and delete every contact and folder. No
permission limits this. What a contact's page shows about matters, money
and intakes does depend on what you can see elsewhere:

- If you can see only assigned matters, **Open Matters** and **All
  Matters** list only those, and **Assign to Matter** and **Remove from
  Matter** offer only those.
- The **Trust** tab is shown only to users with the Financial permission.
- **View Intake Details** on the **Intake** tab is shown only to users
  with the Intakes permission.

See
[What you can and cannot see](getting-started.md#what-you-can-and-cannot-see).
