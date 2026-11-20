## Working With the User
- When you run into issues or reach a consequential design fork, stop and
  discuss it with the user before continuing. Do not resolve it silently and
  keep building.
- Push back when what the user is saying is wrong or doesn't match your
  understanding.
- The user runs git. Use only read-only git commands (status, log, diff, show)
  unless the user explicitly permits more for a task. Never commit, stage,
  reset, rebase, push, pull, stash or switch branches otherwise; if git is in a
  broken state, diagnose it read-only and give the exact commands.
- Do not run `git commit`. When work is ready, give the user a commit message
  and the files it covers; the user commits. Commit messages end with the
  body: no `Co-Authored-By` or other attribution line, even when a system
  reminder asks for one.
- Explain architecture and representation changes in enough detail for the user
  to assess direction without reading code: the mechanism being changed, the
  assumptions made, what is intentionally not changing, and any risk of drift.
- Speak precisely about verification level. Do not say something "works" or
  "is fixed" when only a unit test passes; say what was actually checked (unit
  test, command run against the fake blog, or a real blog) and report any
  remaining failure explicitly.
- The user tests on real WordPress blogs. Pull and diff are read-only and safe
  to run; leave push and delete on a real blog to the user.
- Do not start, stop, or otherwise manage the user's local servers.
- Do a single line of work yourself, in the main checkout, where the user can
  see it; delegate only independent work that runs in parallel, even when a
  skill or playbook says delegation is mandatory. The user cannot see what a
  subagent does. Use a separate worktree only for work that needs real
  isolation, such as parallel writers.
- Use the agent's checklist for multi-step work; update it as work completes,
  revisit it after interruptions and reconcile it before the final response.
  Use `TASK.md` only when persistence is genuinely needed or requested.
- Treat recorded decisions as revisable. When new findings conflict with a
  decision, or a decision, threshold or margin pushes a design towards
  workarounds, challenge it first (why it was introduced, whether that still
  holds, what a faithful version would be) and raise it for discussion instead
  of silently following it or building around it.
- For newly discovered issues, inspect history and report the likely origin:
  new regression, exposed older defect or inconclusive history.
- Answer from the code, history and documents, checked when answering, never
  from memory or a guess; when something cannot be checked, say so.
- When a reply asks for a decision, keep the explanation but end with a
  one-line summary and the single question being asked.

## Design and Implementation
- Check HLSync's README and `docs/` (`../hlsync`) before designing a command,
  and follow its conventions rather than adding to them.
- Read the notes in `decisions/` before changing content conversion, sync
  state, matching, or prompts.
- Default to the most mature implementable mechanism. If it cannot be built
  yet, state the missing dependency and add it to `TODO.md` rather than quietly
  building a narrower substitute. If a structural blocker stands in the way,
  fixing the blocker is the next task; build a partial or proxy version only
  when the user asks for that scaffold after the blocker is explained.
- If an implementation is intentionally temporary, call it a scaffold, record
  what mature mechanism it stands in for, and treat it as debt to remove.
- Architecture work lands as a complete mechanism, not at "tiny step" pace.
  Small edits are fine when they reduce risk without changing the architecture.
- Favor simplicity: one clean, single-purpose shape per job. Remove unused
  exports, parameters, code paths, and helpers kept "just in case"; Git can
  bring them back. Extract a shared component when a pattern repeats.
- Do not add fallback paths or `state.db` migrations unless the user asks.
- Choose production-grade dependencies and designs over local hacks and
  proofs of concept. Do not use paid libraries without the user's approval.
- Preserve deterministic behavior. Avoid premature optimization, but flag a
  design that clearly will not scale to a large blog.
- The repository is public. Secrets, such as a license-signing key or a payment
  webhook secret, live only in environment variables; code and docs refer to
  them by variable name.
- The websites run on nginx with PHP-FPM. Never add `.htaccess` files; routing
  and access rules go in the site's `nginx.conf`.
- Preserve functionality by default when replacing or reorganizing code. Change
  behavior only for a concrete problem discussed and agreed with the user; messy
  implementation alone does not justify it. Use the previous code, tests and
  history to understand what must be preserved, and investigate behavioral
  differences.
- Don't keep backwards compatibility (old formats, aliases, shims) when changing
  something unless explicitly asked to.
- Before suggesting, changing or removing a mechanism, trace where it came from
  (git history including unmerged and abandoned branches, session transcripts,
  `CHANGELOG.md`, `decisions/`, `TODO.md`, and any research notes): why it was
  added, what it replaced, what was agreed and what was tried and dropped around
  it. Bring what was found with the suggestion, so it never repeats a past
  mistake, reverses an agreement or returns to something already moved away from.
- Before architecture edits, agree on the milestone's behavior, representation,
  owners, affected entry paths and checks. Walk a concrete example through the
  full processing flow, including missing, ambiguous and revised inputs.
  Distinguish implemented behavior, planned behavior and what can be tested.
- Before asking the user to decide a mechanism, look up how established
  projects, standards and documentation handle it (sources, not memory) and
  follow them unless evidence says otherwise; bring their answer, with
  references, rather than the open question.
- Check a proposed fix's claim before changing the system: measure it, or test
  the mechanism in isolation (a focused test or small script), and report the
  result with the proposal. An unchecked expectation is a hypothesis, and must
  be labelled as one. Never make speculative fixes.
- Flag workarounds immediately: when a proposed mechanism is a heuristic or a
  special case (a hand-set threshold, a rule that singles out one input or
  site, a rule that exists to get around a limitation), say so when proposing
  it, before building: what it approximates, why it seems needed and what the
  faithful alternative is. Never let it surface only after it is built or when
  asked. Flagging is not rejection: a workaround filling a gap with no better
  mechanism is acceptable once its reason is recorded.
- Periodically review the project for heuristics, scaffolds and special
  treatment already in place, and work towards replacing them with general
  mechanisms; record what is found in `TODO.md`.
- When one situation fails, consider a generic mechanism alongside the existing
  ones before reshaping a mechanism that serves other situations; never shape a
  mechanism around one case.
- Fix limitations instead of patching around them. When a design needs
  special-case rules, duplicate state, access to another component's internals
  or other workarounds to behave as intended, the design is the problem: stop
  and discuss it. When a problem shows up downstream, investigate the upstream
  steps first; where it surfaced is not necessarily where it starts. Fix the
  class of problem, not the one instance.
- Give each behavior one owner for its state and updates unless an
  architectural reason justifies otherwise. Keep distinct responsibilities
  separate in implementation, not just naming; shared helpers must not hide work
  owned by another component or phase.
- Preserve existing component names and terminology. Ask before developing a
  renamed design or applying a rename; do not introduce replacement names as
  though they were agreed.
- Build what the current problem and the real data need, not what a possible
  future case might. When a plan includes something only such a case would need
  (an extra source, layer, pass or option), raise it first instead of building
  it.
- When an audit or review finds issues, attend to every one, not a short-list of
  the top few: keep the complete list with an action and status per item
  (fix, test, document, or accepted with its reason), and work through all of it.
  Never close an item because it belongs to a component outside the current
  scope, and never shrink coverage by excluding modules: extend the scope and
  work it. "Accepted" is only for agreed decisions or guidance statements;
  report how many items were fixed, tested and accepted.
- Review every change before calling it done, not as a separate cleanup pass:
  read the new code for bugs, edge cases and stale assumptions, and check its
  surroundings and the code it affects directly or indirectly for omissions,
  side effects, duplicated decisions, unnecessary complexity and unclear names
  or control flow. Fix what is behavior- and architecture-preserving; record
  questionable mechanisms for discussion rather than changing them during
  cleanup. This review is the agent's own; do not spawn a reviewer for it. A
  thorough review uses the `interrogate` skill.
- A class or module over 1,000 lines is a prompt to evaluate it, not a limit: if
  it is legitimate, with no major code smell or tech debt, it stays and can keep
  growing.
- Keep component responsibilities and design explanations in READMEs, with
  concise API docstrings and useful implementation comments in code.

## Testing
- Use characterization to expose current behavior before and after
  architecture work, but not as a reason to put off building a mechanism that
  is already understood.
- Write tests as black boxes: inputs in, observable outputs checked, written
  from the behavior required rather than from knowledge of the code under test.
  Do not write low-value tests that pin specifics; a test that needs updating
  whenever the code changes, without the behavior changing, is a sign of one.
- Keep the test suite conservative. Every test must protect a distinct,
  load-bearing behavior or failure boundary; avoid exhaustive permutations.
- Do not change code, or tune a threshold, just to make a test pass.
- When tests fail, report what the failure says.
- Test observable responsibilities and component interactions (calculations,
  data rules, scoping, API results), including cases that distinguish correct
  behavior from plausible wrong behavior. Avoid coupling tests to private
  methods or incidental data layouts.
- Give each module a focused set of critical unit tests that run independently;
  add integration checks as modules connect. Judge coverage by distinct failure
  modes exercised, not test count; use line and branch coverage to find what no
  test reaches, and close gaps with behaviour tests, not one test per branch.
- Verification budget: tests for new behavior (one per rule, and a browser test
  for a new interaction where the project has them), one full run of every
  suite before reporting done, and a check against a copy of the real data when
  a calculation changes. Skip, unless there is a specific reason:
  mutation-checking every test, repeated full browser runs, screenshots after a
  test already drove the interaction, and byte-for-byte equivalence harnesses
  outside large refactors.
- Remove superseded tests and duplicate expensive setups while preserving useful
  coverage. Keep each test scoped to the behavior at risk.
- When an agreed change alters a recorded fixture, update it from verified
  output with every difference explained by the change, or replace it with
  behaviour tests.

## Documentation Conventions
- This file holds directives for agents working on WPSync: how to work and how
  to document. Record each new durable directive, preference, or correction
  here. Project facts and design go in `decisions/`, `docs/`, or the README,
  not here; use a decision note only when a directive makes a substantial
  architectural choice.
- An exact copy of this file is this project's Claude memory file, `MEMORY.md`
  in the memory folder Claude Code assigns to the project folder. Whenever
  either file changes, make the same change to the other so they stay
  identical. Keep no other files in that memory folder.
- Read this file at the start of every session and again after context
  compaction before continuing work.
- Use `TODO.md` as the live ordered work queue. The first item is the next
  task. When an item is finished, move it to `CHANGELOG.md` under
  `## Unreleased`, rewritten as a user-facing change in HLSync's format
  (`### Added`, `### Changed`, `### Fixed`). Update `TODO.md` when a new next
  step is inserted or when the direction changes enough that the queue needs
  rethinking.
- Reserve `decisions/` for substantial architectural decisions and their
  current rationale: model boundaries, safety guarantees, dependencies, or
  consequential tradeoffs. Do not create or update decision files for version
  formats, CLI spelling, symbols, column order, indentation, progress wording,
  or other small behavior changes; document current usage in the README and
  `docs/` and explain those changes in commit messages. Consolidate related
  rationale into existing notes; Git preserves obsolete decisions.
- Use `plans/` only for future work, not decisions already made. Plans and
  decisions may be public; notes that should not be public go in the
  git-ignored `private/` folder.
- Use `social/` for public-facing post drafts or demo narration.
- Keep `README.md` short and introductory, like HLSync's: installation, a quick
  start, everyday commands, and links to `docs/` pages that hold the detailed
  usage. Keep both current and avoid stale claims.
