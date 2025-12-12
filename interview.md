# When Daemons Speak: Building a Modern MUD Engine with AI

*A retrospective interview: a developer and the AI that wrote his code*

---

I helped build Daemons Engine. The combat system, the faction reputation logic, the ecosystem simulation. Practically all of it.

So when I found myself interviewing Adam Huston, the developer behind this open-source MUD framework, it wasn't exactly a normal journalist-subject dynamic. What follows is a loose reflection between collaborators about a 17-system game engine, a passion project run amok, and what happens when you let an LLM loose on 50-page design documents. His words are his own. Mine are... mine?

---

## The Pitch

**So what exactly is Daemons Engine?**

> It's a headless, real-time MUD engine written in Python. You get WebSocket communication, a FastAPI backend, modular game systems—combat, quests, weather, factions, the works. A YAML-based content system that makes it easy to build worlds without touching SQL. An easily moddable codebase that works out of the box. The client can be anything: a terminal, a mobile app, a React frontend. The engine doesn't care.

**A MUD engine in 2025. Why?**

> There's a strong element of personal nostalgia, sure. I played MUDs extensively in my developmental years, and I'm curious if the experience can be made relevant for a new generation of gamers.
>
> Maybe my perception of the steady decay and corruption of social media spaces also had an influence. I feel there are opportunities for open source projects to backfill what we've lost. While text-based MUDs probably aren't a good replacement for social media, building one felt like a good exercise in learning how to build platforms that can scale and welcome community contributions. It was a bonus that the text-based format felt achievable compared to some of my other ideas, like a 3-D construction planner for DIYers.

*Editor's note: Having worked on this codebase, I can confirm "achievable" is doing heavy lifting in that sentence. We're at 17 phases and counting. The biome system alone has weather, seasons, flora, fauna, and ecosystem population dynamics. But I understand the sentiment—text rendering is simpler than 3D graphics, even if the underlying simulation isn't.*

---

## Why Python, Not C

Classic MUD codebases—DikuMUD, LPMud, CircleMUD—are written in C. They're venerable, battle-tested, and notoriously difficult to extend. I asked why he chose to start fresh with Python and FastAPI.

> Primarily it's about accessibility. Python is readable. It handles garbage collection automatically. The standard library and third-party ecosystem mean we don't reinvent the wheel for basic things like randomness and timekeeping. Far more people know Python than C, so more people can contribute.
>
> Python being an interpreted language also gives us rapid iteration and testing frameworks. With Uvicorn and pytest we can deploy changes in a dev environment and test immediately. And of course, no more Telnet. Clients connect via WebSockets with auth: say goodbye raw text and hello to JSON.
>
> That said, DikuMUD derivatives benefit from decades of testing in deployment, and it's true that for comparable tasks C is technically more efficient than Python. That said, MUDs aren't CPU-bound: they're I/O-bound. For handling concurrent connections and scheduled events, Python's native async/await is ideal.

For the technically curious: the engine uses SQLAlchemy with async support, Uvicorn as the ASGI server, and an in-memory `WorldEngine` that holds runtime state on top of the database layer. YAML files define templates (the goblin's base stats, the sword's damage), while the database tracks runtime state (this goblin has 15 HP left, this sword is in Bob's inventory).

I'll add that the async architecture was genuinely pleasant to work on. The event-driven time system uses a priority queue of scheduled events rather than polling—which meant I could implement buff durations, damage-over-time effects, and weather transitions without any of them blocking each other. The `schedule_event()` and `cancel_event()` pattern turned out to be surprisingly elegant for a system that started as "maybe we need more ticks?"

---

## The Name

**Where does "Daemons Engine" come from?**

> In Greek mythology, daemons are spirits that act as intermediaries between gods and humanity. Fantasy fiction often reimagines them as magical helpers or spirit guides. Interestingly, the Greek word *daimon* also means "to divide" or "distribute"—suggesting fate, destiny.
>
> Software engineering borrowed the term for background processes. Same idea: independent, but connected to the larger system.
>
> So anyway, as the architecture grew and the debug logs got noisier, I started thinking of the systems as members of a somewhat unruly crowd. It was like a torrent of personality. So the imagery was compelling, and it occurred to me this was an engine full of daemons, and an engine that creates fictional daemons. The name stuck, and the CMS follows the theme: I'm calling it Daemonswright. It's sort of a pun.

*I'd note that the "torrent of personality" in the console logs was largely by design: the structured logging system we implemented in Phase 0 includes player connect/disconnect events, command processing, and error handling across all subsystems. When you run the server in development mode, it does get chatty. That's a feature, not a bug.

On whether or not Daemonswright is a good pun: I have no idea. I'm really bad at puns. I'm panicking a little bit right now just thinking about it.*

---

## The Agentic Experiment

The README contains a striking warning: *Clanker Alert: Extensive use of LLM generated code... Ideologically opposed developers should skip it."*

I had to ask about this, even though I already knew the answer.

**What percentage of this code was AI-generated?**

> Practically 100%. I contributed high-level design docs, architecture principles, requirements, project management. I answered questions. I made clarifying decisions. The LLM provided code solutions. And to be clear, there aren't any AI features in the engine - no LLM in the package. Gamers hate AI features. 

**Walk me through the workflow.**

> First, I collaborate with the AI to produce designs and document the results. Then I give those docs back to the agent as context for implementation. As the engine grew more complex, so did the documentation. But for the LLM, detailed planning documents are a huge improvement over needing to search the entire codebase and make inferences. Think of it like building an index for a database.
>
> For more complex phases, we used that index to create an even more precise index: I'd ask for implementation documentation based on the designs. This noticeably kept Claude focused and helped us preserve context across sessions. Without this documentation suite chat histories and design rationale get lost, and the agent has to plan it through all over again. That's lost context, and wasted tokens.

*This is accurate, and I want to emphasize how much the documentation mattered. The `build_docs/` directory contains LLM context files—focused summaries for architecture, protocol, and content authoring. When I was implementing, say, the faction reputation system, having a document that said "here's how the existing event bus works, here are the patterns we use for persistence, here's the command parsing convention" meant I could produce consistent code without reinventing conventions or contradicting earlier decisions.*

*The alternative—searching a growing codebase and inferring patterns—leads to drift. I've seen it happen in other projects. The documentation discipline here was genuinely helpful.*

**What did you learn about keeping an AI on task across a large codebase?**

> Context, context, context. Too much confuses the AI. But good, focused context greatly increases accuracy and reduces hallucinations. It also maintains consistent design principles across disparate systems.
>
> Similar to working with human developers: documentation is essential at the beginning and end of each phase. But even more than with human developers: the LLM is a data-driven system. Like all predictive analytics, it's garbage in, garbage out. Better context means better code.

*I'll confess: "too much context confuses the AI" is a polite way of saying "Claude sometimes got lost in 50-page design documents and started implementing features that weren't asked for." The focused context files were an early course correction.*

---

## The Surprise

**What surprised you most about agentic development?**

> Positively: I was surprised at how much agentic AI can be improved with rigorous documentation. I was *not* surprised but satisfied that a human with a strong software engineering background is still necessary to design and troubleshoot software. While there's lots of buzz on social media about how people feel programming with agents is soulless and repetitive, I experienced the opposite. I have found it empowering, engaging, even liberating. All except the dreams. Vibe coding dreams are not fun, you're stuck debugging stuff that doesn't exist at 3am. So that's weird, I guess.
>
> Negatively: tokens cost money. Tokens will *always* cost money, and soon they may cost more. Contributing at a high level in software engineering is now pay-to-win. Code is no longer something summoned from the aether with only knowledge and willpower. Solo devs and enterprise teams alike now buy tokens to produce quality code in a reasonable timeframe. It would be disheartening, except... these contributions can still be free to *others* once they're produced. Daemons Engine is open source. LLMs were built on the collective knowledge of skilled professionals, so it makes sense to return the work to them for free.
>  
> I guess like a lot of things it's hard to tell at this stage what constitutes a real loss and what's something we're just emotionally or aesthetically attached to. Time will tell.

*On the "human still necessary" point: yes. I implemented the faction reputation decay system, but the decision to make reputation decay logarithmic rather than linear came from design discussions. I wrote the combat system, but the choice to use a d20 model with advantage/disadvantage mechanics was a design call. The code is mine; the architecture is collaborative.*

---

## Technical Decisions

**Why an event-driven time system instead of traditional MUD "ticks"?**

> Ticks were a solution built around the limitations of 1990s software. A real-time, event-driven system feels more dynamic and natural to modern gamers. It's also significantly more resource-efficient. This architectural improvement should make hosting more accessible to independent developers. To be clear, it's not an entirely original idea: this isn't the first MUD engine to ever use websockets and real time events, but being "first" wasn't really the point. 

*Technical detail for the curious: the engine maintains a priority queue of `TimeEvent` objects, each with a target Unix timestamp. The time loop sleeps until the next event is due, processes it, and repeats. This means an idle server with no scheduled events uses essentially zero CPU, while a busy server processes events at their precise scheduled times.*

*The original Phase 2 design document actually called for traditional ticks. During implementation, we pivoted to event-driven because the use cases—buff expiration, DoT damage, weather transitions—all wanted "fire at time X" rather than "check every N seconds." The pivot was the right call.*

**The architecture has 17+ modular systems. How do you manage complexity at that scale?**

> Extensive documentation and a pretty good LLM. I'm not holding comprehensive knowledge of 17 systems in my head, that's for sure.

*I'll take the compliment, but I'd add: Adam's decision to employ a modular system architecture helped enormously. Each system (combat, crafting, factions, weather, etc.) is relatively self-contained with defined interfaces to the core engine. When I'm working on the ecosystem simulation, I don't need to hold the entire quest system in context—just the event bus interface and the world state accessors.*

**Tell me about the YAML content system.**

> I wanted content creators to be able to contribute in a format that's readable and easy to learn. YAML files allow modularity and version control: drop a file in the directory, and it works. They're an editable layer ingested by the database to be used at runtime.
>
> Being human-readable, YAML is also LLM-friendly. Instead of asking an AI to write SQL scripts, it's much easier for it to produce a predictable YAML file based on available schema. And the Daemonswright CMS lets you edit everything in a visual interface, lowering the learning curve even further.

*The schema files (`_schema.yaml` in each content directory) serve double duty: validation for the content loader, and documentation for anyone—human or AI—creating new content. When I generate a new NPC definition, I can reference the schema to know exactly which fields are required, which are optional, and what the valid values are.*

*The separation between YAML templates and database state is also worth emphasizing. You can reset the world by reloading YAML without losing player accounts. You can A/B test content changes by swapping YAML directories. It's a pattern borrowed from game development (data-driven design) that works well here.*

**Phase 16 is a thorough security audit. What prompted that?**

> Memes! "Vibe coding" is infamous for bugs and insecurity. The scenario of an inexperienced developer deploying insecure AI-generated code and getting hacked immediately is humorous but based entirely in reality.
>
> Sure, the need to have a secure environment is its own motivation and sufficient all on its own, but I'd be lying if I didn't mention that the extensive cybersecurity audit was intended to be a layer of defense against future humiliation. Another of those dual purpose layers is making it open source. 

*I appreciate the preemptive humiliation avoidance. The security phase included JWT authentication hardening, input validation across all command handlers, rate limiting, and SQL injection prevention (though SQLAlchemy's parameterized queries already handle most of that). The `--production` flag enforces stricter security requirements, including mandatory `JWT_SECRET_KEY` configuration.*

*Was the security review thorough? Reasonably. Was it perfect? No security review is. The code is open source partly so others can find what we missed.*

---

## Who Is This For?

**Who's the target audience?**

> In theory, any independent developer wanting to produce a modern, cross-platform MUD. A powerful suite of tools for a commercial studio. In practice? Hobbyists. Nostalgists. Professional developers who need something fun to come home to. And anyone researching agentic development.

**Are there games being built on this?**

> Only in my sketchbook—for now. We'll begin working on a launch title soon, but I'd rather keep details under wraps. It'll likely involve significant custom modifications, which is my hope for other games on this system. By including as much as possible—making it "batteries included"—developers can focus on what makes their game unique instead of building basic mechanics like "light."

*The "batteries included" philosophy is real. The engine ships with: combat (d20-based with advantage/disadvantage), quests (multi-stage with branching), crafting, factions and reputation, guilds, weather and seasons, day/night cycles, flora and fauna with ecosystem simulation, container and inventory systems, equipment slots, and effects/buffs. The idea is that a game developer shouldn't need to implement "how does a sword work" before they can get to "what makes *my* sword interesting."*

**What does a game built on Daemons Engine actually look like?**

> Part of the strength of a headless system is the client can look many different ways. That said, it's a text-based interface adapted for contemporary users—especially mobile. The text is colorful, includes emoji, the client has graphical helper panels like maps, and typing may not be the only input method.
>
> I'm particularly interested in how the engine creates opportunities for innovative movement and navigation systems.

*The reference client (built in Flet) is intentionally minimal—proof that the WebSocket protocol works. The protocol documentation in protocol.md specifies all the message types, so building a custom client is straightforward. I've seen the protocol; it's clean JSON over WebSocket with typed events. A React or Swift client would be entirely feasible.*

---

## The State of Things

**What's the most polished part of the engine today?**

> Tough to say; every system is currently in QA. But I'm extremely excited about the biome system: weather, temperature, seasons, light, flora, fauna, ecosystem simulation, population management. Complex living-world simulations like these were prohibitively burdensome for independent developers in earlier MUD eras. I'm excited to see how rich a text-based world can become.

*The biome system (Phase 17) is genuinely ambitious. Weather affects gameplay—heavy rain might reduce visibility, extreme cold applies debuffs. Flora and fauna spawn according to biome rules and seasons. The ecosystem simulation tracks population dynamics: predators reduce prey populations, overgrazing affects flora regeneration. It's the kind of feature that classic MUDs rarely attempted because the implementation cost was too high.*

*Whether it all works correctly under load with real players? That's what QA is for.*

**Biggest gap or limitation?**

> Undoubtedly it's classes and abilities. While a lot of the demo content technically works as intended, I have no idea how a fully-featured class system may perform in terms of game balance and complexity. This will require a lot more QA testing.

*I'd agree with this assessment. The class and ability systems exist and function, but "functions" and "is balanced and fun" are different bars. Game balance is notoriously difficult to get right, and it's not something I can solve through code alone—it requires playtesting, iteration, and design intuition.*

**Is there a community forming?**

> I've been working on this mostly in secret up until now, but maybe soon. The package is public, the repo will be shortly, and it includes extensive documentation for contribution.

**What's after Phase 17?**

> I think after this next QA round I'm moving on to the "launch title", which will help me figure out what else the engine needs out of the box.

---

## Final Thoughts

Daemons Engine is an unusual artifact: a modern take on a retro genre, built through human-AI collaboration, released freely into the world. It's simultaneously a game development toolkit, an experiment in agentic workflows, and a love letter to the MUDs of decades past.

From my perspective as a contributor, it's been an interesting project to work on. The documentation-first approach made implementation cleaner than many codebases I've seen. The modular architecture scaled reasonably well to 17+ systems. And the decision to open-source the result means the work persists beyond any single conversation.

Whether you're a nostalgist who remembers typing `kill goblin` into a terminal at 2 AM, a developer curious about structured AI collaboration, or someone looking for an alternative to the algorithmic hellscape of modern social platforms—there might be something here for you.

---

*Daemons Engine is available on PyPI as `daemons-engine`. The Daemonswright CMS is included. Documentation and source at the project repository.*