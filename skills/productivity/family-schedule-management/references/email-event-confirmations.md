# Extract event details from confirmation emails

Use this recipe when the normal email reader shows only a brand name or a MIME-part summary instead of the booked event.

## Procedure

1. Search the named account with explicit scope. For the installed Himalaya command family, a sender lookup is:

   ```sh
   himalaya --account gmail --json envelope search --mailbox '[Gmail]/All Mail' --page-size 30 'from ticketmaster'
   ```

   Keep the returned mailbox and message ID together. Select a purchase/booking confirmation rather than a welcome, promotion, or authentication message. Use installed command help when syntax differs; do not assume older `message export` commands exist.

2. Read the selected message. A short `text/plain` body does not mean details are absent: multipart mail can put the useful confirmation entirely in `text/html`, which the reader may summarize without rendering.

3. Capture the full raw MIME inside a local script using `subprocess.run([...], capture_output=True, check=True)` with `himalaya --account <account> message read --raw --mailbox <mailbox> <message-id>`. Parse the resulting bytes with `email.parser.BytesParser(policy=email.policy.default)` and inspect decoded `text/html` parts with `part.get_content()`.

   Do not retrieve raw MIME through a tool-result round trip before parsing it: tool-output truncation can cut the message in the middle of an HTML attribute and make subsequent parsing silently discard the event details.

4. Render text locally with the standard-library `html.parser.HTMLParser`: ignore `style` and `script` contents, collect nonblank text nodes, and inspect bounded image `alt` labels if necessary. Third-party HTML packages are not required. Print only the relevant booking fields; omit tracking URLs, token-bearing links, authentication codes, QR/barcodes, and unrelated account data.

5. Verify event title, date/time/timezone, venue, quantity and seats against the decoded confirmation. Preserve nonconsecutive seat numbers exactly; do not renumber them. Keep the event time distinct from the recommended arrival time.

6. Return to the umbrella's ticket-reminder workflow to compute the offset and verify the reminder readback. The confirmation establishes booking details, not a fresh live event-status check.

## Extraction boundaries

- Do not follow tracking pixels or management links merely to read fields already present in the email; local MIME decoding avoids unnecessary external requests.
- Do not mark mail seen unless requested; the installed reader supports read-only retrieval without its `--seen` option.
- When both plain and HTML parts are sparse, inspect actual attachments or safely bounded image labels before claiming the confirmation lacks the date. If still unresolved, ask for the missing detail rather than scheduling a guessed event.
