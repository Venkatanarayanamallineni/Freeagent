# say2 accuracy test

**Site:** https://say2.onrender.com/static/demo/dawn/index.html  
**Model:** nvidia/nemotron-3-super-120b-a12b on Nebius Token Factory  
**Date:** 2026-10-16

| Check | Result |
|---|---|
| Overall | **40 / 40** (100%) |
| Correct answers (site has the answer) | 26 / 26 |
| Admits it doesn't know (site doesn't say) | 9 / 9 |
| Handles things the business doesn't sell | 5 / 5 |
| Made-up prices or links found | **0** |
| Average time per answer | 1.8 s |
| Average tokens per answer | 3,309 |
| Average cost per answer | $0.0005 |

Made-up check: every $ amount and link in every answer is matched against the site's own text. Anything not found there counts as made up.

