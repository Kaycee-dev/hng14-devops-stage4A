# Code-With-Me Protocol

The goal is not only to ship SwiftDeploy. The goal is to understand and defend every design choice under interview pressure.

## Before Each Implementation Slice

Record:

- what the slice builds
- the DevOps concept behind it
- the exact files in scope
- the expected behavior
- the main failure mode to watch for
- the interview answer that justifies the approach

## During The Slice

- Explain commands before running them.
- Keep changes within the active packet.
- Capture failed commands and the diagnosis.
- Do not move to adjacent work just because it is nearby.

## After The Slice

Record:

- evidence command and result
- what changed in plain English
- what the operator should be able to explain
- new interview questions and answers
- unresolved risks or follow-ups

## Teach-Back Gate

A slice can close only when the operator can explain:

- what problem the code solves
- why the chosen approach fits the brief
- how to verify it
- what breaks if the implementation is wrong

