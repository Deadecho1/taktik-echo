# Search recovery after exhausted post scroll regions

After gallery recovery, the live session encountered a collapsed search screen
where the only recognized post occupied a thin bottom strip. Its scroll area
contained no safe gesture rectangle. `scroll_region` chose that nonempty list
and ignored independently parsed navigation areas, including a safe left margin.
This caused both advancement and all startup retries to fail with
`No continuous X scroll region excludes nested controls and media`.

The selector now prefers post scroll regions as before, then tries verified
navigation areas when the post regions have no usable path. Both choices retain
control/media exclusions and the existing minimum dimensions. No gesture is
offered if neither choice is safe. Movement verification, query continuity,
account verification, uncertainty handling and deadlines remain unchanged.

The normal Android hierarchy reproduces the exact failure. A captured regression
checks the safe margin and header-recovery path, plus rejection when that margin
is covered. The fixture manifest records original and anonymized hashes.
All 2,055 X tests passed after the change. Ruff, whitespace and the tree-layout
audit also passed.

The old debug job had exhausted its retries and stopped automatically. Recovery
uses the ordinary Echoseek controller to register a replacement debug job with
the same original end time, leaving its current post-debug stop intent intact.
