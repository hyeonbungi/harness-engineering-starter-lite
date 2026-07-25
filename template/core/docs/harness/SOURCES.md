# Source Attribution

This Core profile is an adapted implementation informed by:

- Walking Labs, **Learn Harness Engineering**
- Source: <https://github.com/walkinglabs/learn-harness-engineering>
- Course: <https://walkinglabs.github.io/learn-harness-engineering/ko/>
- License reported by the locally mirrored course index: MIT

The installed `docs/harness/source-map.json` resolves all 65 `SRC-*` identifiers
without requiring access to the starter repository or the original Obsidian
vault. It records each source's original relative path, role, disposition,
rationale, and broad linked targets. Those targets include installed `HC-*`
components and named future modules or fixtures. `docs/harness/components.json`
records the narrower direct source provenance for each installed component.
Every direct component source must appear among the source row's broad targets;
the reverse does not imply that every influenced target treats the source as a
direct basis. `source-map.json.link_semantics` preserves this distinction for
machine readers.

The profile adapts operating principles and selected template patterns; it is
not a verbatim copy or an official Walking Labs distribution. `LICENSE` covers
this starter distribution, while `NOTICE` preserves attribution and explains
the boundary for separately redistributed upstream material.

Project-specific decisions added after adoption should name their own source,
application trigger, validation, review trigger, and rollback path.
