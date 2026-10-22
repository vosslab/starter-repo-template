# Human guidance

<!-- VENDORED HEADER: START -->
Record the durable guidance Neil Voss states, or approves for preservation here, in his own words:
first person or close paraphrase, one to three lines per bullet. Material he supplies as a source
may inform [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) once it is settled, and an entry of uncertain
origin belongs there too. Rules: [REPO_STYLE.md](REPO_STYLE.md).
[PROPAGATED HEADER - ENTRIES BELOW ARE YOURS]
<!-- VENDORED HEADER: END -->

- Use plain, concrete language and direct sentences. Vocabulary and jargon are liabilities as
  well as assets; use technical terms when they add precision or clarify an established concept.
  Write for clarity, not sophistication. When in doubt, use the simpler word.
- Shorter variable names do not make code faster. Use a longer variable name when it offers
  more clarity.
- Make durable changes in starter-repo-template; consumer copies are vendored.
- A temporary, easily removable wrapper is acceptable for the Graphify crash.
  Make the edited node count match the expected normalized count.

- I prefer the latest software versions. Current security and bug fixes take priority over
  supply-chain concerns; never pin versions, and use `>=` if a version constraint is required.
- I prefer the library folder and executable to start with different characters so autocomplete
  can distinguish them without typing a long shared prefix.
- Apply KISS aggressively: prefer the smallest coherent design that meets actual requirements and
  known failure modes. Add mechanisms, abstractions, policies, state, and tests only for a
  demonstrated need. Complexity should earn its place.
- Overengineering for edge cases has been a huge problem lately. Make avoiding speculative
  edge-case machinery an explicit priority in implementation and review.
- Reviews should justify added complexity against concrete requirements, demonstrated failures,
  or meaningful risks, including implementation, testing, documentation, and maintenance costs.
  Simplify unnecessary code; when the existing plan is sufficient, say so and let the manager proceed.
- Keep configuration simple and prefer sensible fixed internal behavior. Add choices only for
  demonstrated needs; first consider whether shared behavior can handle caller differences
  automatically or whether the tasks are genuinely different. Favor the simpler shared design.
