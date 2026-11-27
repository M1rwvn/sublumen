# Sublumen user guide
Sign in with the admin account you set through `SS_ADMIN_EMAIL` / `SS_ADMIN_PASSWORD`.
- **Stego Studio:** pick a cover image (PNG or BMP), type a message and a password, choose Embed, download the result. To read it back, upload the stego image, enter the password, choose Extract. The image must stay byte for byte as downloaded: JPEG conversion, resizing or screenshots destroy the message.
- **Cases & Evidence:** create a case, upload an image (it is hashed with SHA-256 and stored read-only), press Analyze. The result shows a model score gauge (0.5 is the validation threshold), a per-tile overlay (amber tiles carry more model evidence; it shows where the score comes from, not where a message is), and the classic indicators with a short "What is this?" explanation each. There is never a verdict: indicators are leads. Generate PDF report makes a PDF report with the hashes, results and limitations; Audit trail lists every action.
- **Visual Lab:** bit planes, an RS anomaly heatmap and the model overlay for an evidence ID.
- **Compare:** two images, with SSIM, PSNR and a difference map.
- **Models / Benchmark Lab:** which models exist, how they were measured, and their limits.
Reading the score: low does not prove an image is clean; high does not prove it hides data. Calibrate on clean images from your own source. Not tested: third-party stego tools, JPEG-domain stego, camera RAW.
