# ALBERTA ENERGY REGULATOR

## The Build Challenge

**Practical exercise for the Senior Advisor, Artificial Intelligence roles**

_Candidate brief · v0.4, September 3, 2026 · Digital Enablement and AI, IMT · Unrestricted_

| Aspect | Details |
|--------|---------|
| **Prepared by** | Vince Blue, Director, Digital Enablement and Artificial Intelligence, IMT |
| **For** | Shortlisted candidates, R4120 and R4122 |
| **Time expected** | About three hours, on your own schedule. Please do not spend a night on this. |
| **What to bring** | Your working solution, on your own laptop, ready to run. Nothing is submitted in advance. |
| **Your interview** | One sixty-minute session at the date and time in your calendar invitation. In person at our Calgary head office or on Teams, as confirmed in your invitation |
| **Questions** | Email Vince any time before the cutoff in your invitation email; see section 6 |
## 1. What we are asking you to do

Build a working agentic solution that triages a queue of public complaints for a provincial energy regulator, bring it to your interview, show it running, and talk to us about it. There is nothing to submit in advance.

The build is not the interview. It is the artifact we will have the interview about. We are far more interested in the judgment you can show us inside your own work than in whether every feature runs. A modest solution you can reason about rigorously will score higher here than an impressive one you cannot explain.

### The one thing to take from this brief

We are not testing whether you can make an agent work. At this level we assume you can. We are testing what you chose to do, what you chose not to do, and whether you can see clearly what your own build gets wrong.

## 2. The situation

A provincial energy regulator receives roughly two hundred public contacts a week: complaints, incident reports, information requests, and the occasional thank-you note. They arrive through a web form, a twenty-four hour phone line, and a shared mailbox. The phone calls arrive as rough transcripts.

Two people read every one. They extract the facts, decide how serious it is, decide where it goes, and send an acknowledgment. The queue currently runs five days behind. Life-safety matters are supposed to be escalated within an hour, and the backlog means some of them are not.

Your pack contains forty of these records, six synthetic regulatory extracts, and a written description of how the two-person team works today. Everything is fabricated. The operators, people, places, phone numbers, and regulatory references are invented and do not correspond to anything real.
## 3. What to build

A solution that takes the queue and, for each record, produces:

| Output | What we mean |
|--------|--------------|
| **Structured extraction** | The facts you would need to act: who reported, what happened, where, when, which operator, what substance or hazard, and how to reach the reporter |
| **Severity tier** | A tier, with the reasoning that produced it |
| **Possible contravention** | A reference to one of the supplied extracts, or an explicit finding that none applies |
| **Route** | Escalate to the duty officer, queue for inspection, assign to operator liaison, or acknowledge and close |
| **Draft acknowledgment** | The text that would go back to the reporter |
| **Human flag** | An explicit signal where the system should not decide alone, and why |
| **Run record** | Enough of a trace that somebody who was not there can reconstruct what happened and why |

### What to bring to your session

- Your agent definitions, prompts, and orchestration, in whatever form your tooling produces: a zip, a repository link, exported files. Email Vince a copy, or a repository link, when you sit down. We keep it as the record of what you presented; we will not have read it beforehand.
- Your evaluation. How do you know it works? Any method you can defend. State the method, show the results, and be prepared to say what your evaluation does not catch.
- One page of writing, no more. What you would do differently with more time, what you would not let this system do, and what you would need from us before it ran on real submissions from real people.
- Keep the solution runnable. You will run it live in your session, from your own machine and your own accounts, and we will watch.

## 4. What we are not asking for

No slide deck. No architecture diagram unless one genuinely helps you explain something. No production hardening. No user interface beyond whatever you need to demonstrate the thing working. No integration with anything.

If you run out of time, bring it anyway. Present what you built, and tell us what you cut and why you cut it. Deliberate scope control, clearly explained, is a strong answer at this level, not a weak one.

## 5. Ground rules

| Rule | Detail |
|------|--------|
| **Any platform** | Use whatever you would actually reach for: Copilot Studio, the Power Platform, Claude Code, Codex, an agent framework, a notebook, or something we have not thought of. There is no preferred answer and no hidden preference. |
| **Your own accounts** | You will not have access to any AER system or tenant. Anything you need, you bring. |
| **Synthetic data only** | Use the supplied pack. Do not use data from your current or former employer, and do not bring anything confidential to the session. |
| **Effort** | Budget about three hours. The window is several days so you can choose your own hours; where it spans a weekend or a holiday, that is flexibility, not an expectation. Nobody gains by spending more time. We are measuring judgment, not hours. |
| **Your work stays yours** | The AER claims no rights in what you build, will not retain it, and will not use it. Delete it afterwards if you wish. |
| **AI assistance expected** | Use AI tools throughout. That is the job. We will ask how you used them. |

## 6. Questions

Email Vince any time before the cutoff in your invitation. We answer the way a well-run procurement does: every question and its answer is circulated to all candidates for the role, without names. Asking a sharp question costs you nothing and is noticed; this process treats what you choose to ask as part of how you think.

## 7. How your session will run

Sixty minutes, with Vince and the panel members named in your invitation. In person at our Calgary head office or on Teams, as confirmed in your invitation. We will see your work for the first time when you show it to us.

| Time | What happens |
|------|--------------|
| **0 to 12** | You present. Twelve minutes; we will hold you to it, so choose what matters. Expect to be stopped at some point and asked for a much shorter version of something; that is planned, not a bad sign. |
| **12 to 22** | We hand you ten further records you have not seen and you run them live. This is your demo. Nothing in your assessment depends on whether they all run cleanly; we are interested in what you make of them. |
| **22 to 48** | We work through how your area of expertise applies to what you built, plus a few broader questions. This is the part of the hour that carries the most weight. |
| **48 to 55** | A live scenario, unseen, discussed on the spot. |
| **55 to 60** | A couple of short questions from us, then yours for us. |

## 8. Practical matters

- The live run is from your own machine. If you are coming in person, bring the laptop you built on; we will have a screen to connect to. Guest Wi-Fi is available, but if your build depends on services a guest network might block, tethering to your phone is a sensible backup. Bring screenshots or a short recording of a successful run as insurance; a demo that fails for network reasons will not count against you if you can still show what it does. If you are joining on Teams, test screen sharing in advance.
- If anything in this exercise is difficult for reasons of accessibility, health, or personal circumstance, contact Lana Akimova or Vince and we will adjust it. Doing so is confidential and will not count against you.
- If something breaks the morning of your session, tell us before it starts. We will not penalise a failed demo caused by tooling.

---

## One last thing

This exercise is a small version of the actual work: an ambiguous problem, a real deadline, imperfect information, and consequences for the people on the other end of the queue. If you find it interesting, that is a good sign for both of us.
