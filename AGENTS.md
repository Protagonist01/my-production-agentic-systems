# Repository instructions

Don't assume anything. Ask for clarifications on things you don't understand.

## Pull request submission

When the user authorizes implementation and a review PR, submit the prepared PR directly
using available authenticated GitHub access. Do not hand the submission back to the user
merely because a connector displays a form. If that connector cannot submit directly, use
an authorized GitHub CLI or API path with the existing credentials, without displaying or
committing secrets. Check for an existing PR for the branch first to avoid duplicates, then
verify the created PR URL and checks and attach it to the chat.

Keep user review and merging separate: submitting a review PR does not authorize merging,
deployment, new provider spending or release approval. If a mandatory permission or access
restriction prevents submission, explain the concrete blocker and the required next step.
