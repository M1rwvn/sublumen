# Limitations (read before trusting a score)
1. **Detection is statistical.** A HIGH score is a lead, not proof; a LOW score does not prove an image is clean.
2. **False alarms depend on the photo type.** Default v7 flags 1.6-2.3% of clean Imagenette-160 crops and 7.5% (95% CI 5.5-9.7) of clean full-size photo crops; v6 flagged 28.7% of the same full-size crops. On 3 extra photos (120 crops, noisy) v7 flagged about 17% (one photo 42%). Calibrate on your own clean covers before relying on the score.
3. **LSB matching** (+-1 changes) is caught 37-62% of the time at 25-50% payload (v7); at low payloads it is mostly missed. Replacement at 10% payload: 43-55%.
4. **JPEG:** hiding data in a PNG and then converting to JPEG destroys the message (and Sublumen says so). Detection on recompressed images is weak (v7 recall 6-16%, with about 2% false alarms on recompressed clean covers) and the detector cannot analyse JPEG DCT-domain steganography at all.
5. **Data:** training and tests use Imagenette crops (ImageNet-derived, 128x128 crops of 160px and full-size photos) plus synthetic covers. There is no BOSSBase or other external benchmark, and no CNN (no GPU/torch in the build environment).
6. **Payload bits in benchmarks are random** (equal to ciphertext), which is the realistic case for an encrypted message but not for plain-text hiding tools.
7. **Not verified:** `docker compose up` itself, real C2PA signatures from a trusted CA, HTTPS, a WCAG audit, browsers other than Chrome, real mobile devices.
8. **Model switching:** the default is `model_v8_hgb` (see the v8 locked test in the README; trained on 128px crops, full images are scored on up to 8 tiles; JPEG-recompressed stego is mostly missed); `model_v7_svm_rbf` and older models stay selectable for comparison.
