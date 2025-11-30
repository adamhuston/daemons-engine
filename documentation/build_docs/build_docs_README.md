# Build Documentation

## Purpose

This directory contains **phase design documents** that guide our agentic AI development process. Each document serves as a comprehensive specification that AI coding assistants (like GitHub Copilot, Claude, or ChatGPT) can consume to understand requirements, architecture decisions, and implementation details for a specific feature phase.

## How We Use These Documents

### 1. **AI-First Development**
These documents are written in a format optimized for Large Language Model (LLM) comprehension:
- **Executive summaries** provide quick context
- **Current state analysis** helps AI understand existing code
- **Detailed specifications** reduce ambiguity and hallucinations
- **Implementation phases** break work into concrete, testable chunks
- **Design decisions** explain the "why" to prevent AI from suggesting anti-patterns

### 2. **Single Source of Truth**
When working with AI assistants:
1. Reference the relevant phase document in your prompt
2. AI reads the design decisions and architecture
3. AI generates code that aligns with project patterns
4. AI suggests tests based on success criteria
5. AI can validate implementation against design goals

### 3. **Iterative Refinement**
As we build:
- Phase documents evolve based on implementation learnings
- "What We Already Have" sections are updated after each phase
- Design decisions capture trade-offs made during development
- Future phases reference completed phases for consistency

## Document Structure

Each phase document follows this template:

- **Executive Summary**: High-level overview and key principles
- **Current State Analysis**: What exists, what's missing
- **Design Philosophy**: Core architectural principles
- **Proposed Architecture**: Data structures, systems, interfaces
- **Command Integration**: User-facing commands and syntax
- **YAML Content Layer**: Configuration examples
- **Design Decisions & Rationale**: Why we chose specific approaches
- **Implementation Phases**: Ordered, testable sub-phases
- **Testing Strategy**: Unit, integration, and edge case tests
- **Success Criteria**: Measurable completion goals

## Example AI Workflow

### Design Phase (Collaborative)
```
Developer: "Let's design the social systems for Phase 10"

AI Assistant: *Collaborates on design document*
- Analyzes current architecture (from previous phases)
- Proposes data structures and patterns
- Discusses trade-offs and design decisions
- Iterates on specifications based on feedback
- Documents rationale for future reference

→ Result: PHASE10_design.md created through dialogue
```

### Implementation Phase (Guided)
```
Developer: "Now implement group creation from Phase 10.1"

AI Assistant: *Reads completed PHASE10_design.md*
- Understands GroupSystem architecture (we designed together)
- Sees group create command spec
- Notes event-driven communication principle
- Checks backward compatibility requirements
- Generates code matching documented patterns
- Suggests unit tests from testing strategy section
```

### The Key Insight
**We design together, then build together.** The design document becomes our shared memory—capturing decisions made during collaborative design sessions so the AI (and future developers) understand not just *what* to build, but *why* we chose this approach.

## Benefits

✅ **Reduces context switching**: AI doesn't need to explore entire codebase
✅ **Maintains consistency**: All generated code follows documented patterns
✅ **Enables parallel work**: Multiple AI sessions can work on different phases
✅ **Preserves intent**: Design rationale prevents accidental anti-patterns
✅ **Accelerates onboarding**: New AI assistants (or humans) understand decisions quickly


**Note**: These documents are living specifications. Update them as you build to keep AI assistants aligned with actual implementation.
