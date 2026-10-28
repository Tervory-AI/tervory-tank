# trigger.languagetool

## 1.0.0
- First version. Pins LanguageTool 6.8 (image `meyay/languagetool:6.8-13@sha256:062924c66c649d706d60aed80af6bab207bb50a053733e7ac1ca0d8446d150f1`) as the checker the room calls. This package maps that v2/check JSON into `{source: languagetool, rule, message, offset, length}` findings, including incomplete and unavailable states. No model. Eval fixtures are saved LanguageTool JSON, not live network.
