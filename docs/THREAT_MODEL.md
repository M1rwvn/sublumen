# Threat model
**Assets:** hidden messages (confidentiality), evidence files and reports (integrity), user accounts, the server.
**Actors:** a curious third party who obtains the stego image; an attacker who uploads hostile files; a forensic analyst who must not alter evidence; a user with a weak password.

| Threat | Mitigation in Sublumen | Residual risk |
|---|---|---|
| Third party reads the hidden message | AES-256-GCM, key from Argon2id (time 2, 19 MiB), random salt and nonce per embed | Weak passwords can be guessed offline; the file format has a recognisable header, so a message is hidden from the eye, not from a determined analyst |
| Message tampered or wrong key | GCM tag check, clear error | None known |
| Image is detected as stego | Keyed-order mode spreads changes; low payload helps | A statistical detector can still flag it (see LIMITATIONS); LSB methods are weak against modern steganalysis |
| Hostile upload (huge, malformed, wrong type) | Magic-byte sniffing (PNG/BMP/JPEG only), byte cap, pixel cap, decoding errors handled, random server-side filenames | Image libraries can have their own bugs; keep Pillow updated |
| Evidence altered after intake | SHA-256 at intake, originals stored read-only, duplicate detection, audit trail, report built from stored rows | A server admin with filesystem access can still change files; hashes make this detectable, not impossible |
| Credential guessing | Argon2id password hashes, login rate limit, signed expiring tokens, roles | Rate limiter is in-process memory (resets on restart, per worker) |
| Secret leakage | Passwords are never stored or logged; stack traces stay in the server log; secret from `SS_SECRET` | Tokens are bearer tokens in browser storage; XSS would expose them (React escapes output) |
| Transport interception | None built in | Run behind HTTPS (NOT configured here) |
| False accusation from a score | No verdict wording, limitations on every result and in the PDF | A user can still misread a score; keep the limitations visible |
Out of scope: nation-state adversaries, side channels, malware on the analyst's machine, DCT-domain (JPEG) steganography.
