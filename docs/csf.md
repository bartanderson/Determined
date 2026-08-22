The Component Substitution Fallacy
Systems thinking for code analysis tools

The component substitution fallacy (David Woods, cognitive scientist and systems expert) is the mistaken belief that you can make a complex system reliable simply by finding and fixing its broken, weak, or defective individual components.

Core Ideas

System vs. Parts: It assumes system failure is caused by a single bad part rather than complex interactions.
Latent Defects: Real-world systems always contain hidden flaws and weak links due to everyday trade-offs and finite resources.
Emergent Behavior: Failures happen because of how parts interact under pressure, not just because a single part is imperfect.

Why It Is a Fallacy

Misdiagnosing Root Causes: Blaming a specific "root cause" component lets people ignore messy system-wide problems.
False Sense of Security: Fixing one weak part does not make the overall system safe, because other hidden flaws remain.

How to Find System-Level Errors

Perform Resilience Engineering Audits: Do not look for what went wrong; map out how the system normally succeeds despite everyday pressures and resource limits.
Trace System Interactions: Map the dependencies between components to see how a change or failure in one area ripples across the entire network.
Conduct Post-Mortems Without Blame: Remove human error or "bad parts" as acceptable root causes. Focus instead on the systemic factors, mixed signals, and pressures that allowed the failure to occur.
Identify Latent Conditions: Look for hidden gaps in your organization or technology -- like outdated documentation, conflicting goals, or alert fatigue -- that sit dormant until triggered.

How to Avoid the Fallacy

Adopt System-Level Thinking: Remind yourself that complex systems are inherently flawed and that safety is an active, ongoing process, not a static feature you can install.
Question "Root Cause" Conclusions: When a post-incident report stops at a single broken component or human mistake, ask what system-wide vulnerabilities allowed that specific point to fail.
Expect Emergent Behaviors: Accept that when you combine complex parts, they will interact in unpredictable ways that cannot be foreseen by looking at the components individually.
Value Proactive Learning: Study normal, everyday operations to understand how your system handles stress, rather than only analyzing the system after a major breakdown happens.

Practical frameworks used by safety professionals to map these interactions: STAMP (Systems-Theoretic Accident Model and Processes) and FRAM (Functional Resonance Analysis Method). These map interactions and feedback loops rather than tracing failure to a single broken part.

How this applies to Determined

Determined analyzes codebases. The fallacy appears in two failure modes for a tool like this:

1. Single-module diagnosis: Presenting one module as the locus of a problem when the problem is actually an interaction pattern across several modules. The graph_edges table exists precisely to let Determined trace these interactions -- a low-quality signal on module A that co-varies with a dependency edge to module B is a relationship finding, not a component finding.

2. Root-cause stopping too early: When a gap is identified (stub coverage, cohesion score, call depth), the synthesis layer must ask whether the gap is emergent -- produced by how modules combine -- rather than intrinsic to one module. If the gap disappears when you remove a dependency edge, the edge is the finding.

The synthesis output should name the interaction when the interaction is the cause. Naming the component alone is the fallacy.

Relationship to the Shape of the System

Tenet I (Locality of reasoning) and the component substitution fallacy are in productive tension: locality asks you to reason about one part at a time, while the fallacy warns that reasoning about one part at a time misses emergent failures. The resolution: use locality for construction (writing correct parts) and interaction analysis for diagnosis (explaining failures). Never collapse the latter into the former when something goes wrong.

Sources

- surfingcomplexity.blog/2026/08/19/github-autoscaling-and-the-component-substitution-fallacy/
- surfingcomplexity.blog/2023/04/15/missing-the-forest-for-the-trees-the-component-substitution-fallacy/
