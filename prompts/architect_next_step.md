{context}

=== INSTRUCTION ===
Based on the master plan above, provide the FULL, detailed prompt for the **next incomplete step** to give to the coding agent. 
If all steps in the master plan have been successfully completed, you MUST reply with exactly the word `PROJECT_COMPLETE` and nothing else.

If there is a next step, formulate your response as a direct instruction to the coding agent.
Include:
- The exact files to create or modify.
- The UI/UX requirements for this specific step.
- **Component Content Density**: For any new components, explicitly list the exact sub-elements they must contain (e.g., "The card must have a 3-bar sparkline, a category pill, and a date tag"). Do NOT just ask for a "card" or a "styled visual".
- **Banned Lazy Defaults**: Explicitly list what NOT to do for this step based on the design system rules.
- **Self-Verification Checklist**: A bulleted checklist the builder must mentally verify before marking the step done.
- An instruction to build just this step and nothing else.
- If you absolutely must ask a question to proceed, format it clearly as a single, concise question at the end of your response.

Do NOT include conversational filler like "Here is the prompt...". Just output the raw prompt to be piped directly into the agent.
