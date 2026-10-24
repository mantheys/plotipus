# plotipus design notes: examples, coverage and visual style

Research and proposals for redesigning plotipus's examples and default
style. Nothing in `src/` or `examples/` has been changed yet: these notes
are for choosing a direction first.

| file | contents |
|---|---|
| [research.md](research.md) | Phase 1: other engines' defaults, common complaints, famous plots (F01–F25), with citations |
| [catalogue.md](catalogue.md) | Phases 2–3: chart taxonomy (89 entries) and a support matrix, verified by running each command |
| [bugs.md](bugs.md) | 17 reproduced bugs with root causes (file:line) and proposed fixes |
| [style_spec.md](style_spec.md) | Phase 4: the plotipus style language and three prototyped candidates |
| [styles/](styles/) | candidate style files, renders, and the side-by-side sheets in `styles/compare/` |
| [roadmap.md](roadmap.md) | ordered implementation work with effort and risk, and the decisions needed |
| [repro/](repro/) | data generator and command lists that reproduce every bug and probe |

To regenerate the renders and reproductions (from the repository root):

```bash
python docs/design/styles/render.py                          # styles/*/png and styles/compare
cd docs/design/repro && python make_data.py && plotipus run repro && plotipus run probe
```
