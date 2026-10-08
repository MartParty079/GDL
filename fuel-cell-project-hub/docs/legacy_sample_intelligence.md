# Legacy sample intelligence acceptance

Version: 0.3.1 -> 0.3.2 (PATCH). The historical 0.2.2 target was not used because the repository is newer.

Actual local archive metadata was classified; source files were not renamed, moved, overwritten or deleted. Additive SQLite schema 5 creates aliases, many-to-many sample links, image assets/categories/families and decisions beside existing research objects. Migration made an index backup first. Existing IDs, FTS, objects and overrides remain preserved.

Classification uses qualified repeated naming, filename priority over folder context, configurable taxonomy, confidence and explanations. Numeric fragments alone do not identify a specimen. Condition names describe observed group labels; no scientific pressure/material values were inferred. Manual decisions persist across rescans and may be explicitly reset. Unknowns and missing originals stay reviewable.

Images support All Images / Image Families, combined sample/category/subcategory/extension/date filters, sorting, immediate family preview switching and existing side-by-side comparison. Samples use wrapping cards with current/legacy/all scopes and related Images/Reports/Data/Files tabs. File sizes use decimal bytes and up to three significant figures through one shared helper.

Metadata records: 172,284; samples: 11; links: 55,714; families: 29,252; derived links: 35,102; uncertain/unknown/original-missing images: 31,379.

| Sample | Supported aliases | Images | Reports | Data |
| --- | --- | ---: | ---: | ---: |
| 1344 Pascal | 1344Pa, 1344 Pascal | 5525 | 92 | 2437 |
| 30% 1 Pass | 30% 1 Pass | 4155 | 37 | 1529 |
| 30% 2 Pass | 30% 2 Pass | 1209 | 23 | 520 |
| 30% 3 Pass | 30% 3 Pass | 1787 | 24 | 715 |
| 30% 4 Pass | 30% 4 Pass | 1203 | 23 | 516 |
| 30% 5 Pass | 30% 5 Pass | 2483 | 68 | 1189 |
| 30% 10 Pass | 30% 10 Pass | 1687 | 19 | 672 |
| 15% 1 Pass | 15% 1 Pass | 2375 | 15 | 1079 |
| 3300 Pascal | 3300Pa, 3300 Pascal | 223 | 1 | 120 |
| 4738 Pascal | 4738Pa, 4738 Pascal | 2351 | 15 | 1080 |
| Holy GDL | Holy, Holy GDL | 9538 | 167 | 4151 |

## Holy GDL

Discovered and available as a Legacy sample card. Real search, sample filtering, family links, combined Generated + PNG filtering/sorting and preview passed. Open File and Show in Folder dispatched successfully; separate external application visual confirmation remains unperformed.

Images 9538; originals 2184; generated 5787; overlays 0; pore maps 932; outlines 940; reports 167; data 4151; linked derivatives 3763. Zero overlays is an actual classification result, not a fabricated output.

## 1344 Pascal

Discovered and available as a Legacy sample card. Real search, sample filtering, family links, combined Generated + PNG filtering/sorting and preview passed. Open File and Show in Folder dispatched successfully; separate external application visual confirmation remains unperformed.

Images 5525; originals 1232; generated 3368; overlays 0; pore maps 559; outlines 563; reports 92; data 2437; linked derivatives 2249. Zero overlays is an actual classification result, not a fabricated output.

## Verification

The broad source regression run executed 223 tests, with two explicit baseline skips; that run included 12 duplicate fixture tests introduced by a test import, subsequently removed. Four new classification tests and the existing workspace/index regressions pass. Source smoke exercised 21 workspace screens. Real UI acceptance opened five actual sample workspaces and their Images/Reports/Data tabs, and checked Holy GDL and 1344 Pascal at 1024, 1280 and 1600 pixel widths with visible Details, real previews and Windows file actions. UI screenshot review prompted shorter relationship controls and name-first sample filters.

Microsoft login remains unchanged; its route was excluded from regression execution at the user's request. Password login remains the intended authentication path. Installer packaging derives the canonical version; a source push does not publish a GitHub Release or update an installed app.

## Review items

Automatic associations remain hypotheses until confirmed. Unknown purposes, orphan generated files and ambiguous originals are not discarded or hidden. Two formats of the same explicitly named original prefer TIFF as the representative; distinct acquisition/processing runs remain separate. Reclassification can be cancelled and reuses file signatures. Transient file hydration is limited to explicitly selected previews; no bulk downloads occurred.
