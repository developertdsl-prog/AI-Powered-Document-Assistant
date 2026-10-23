# Milestones

This project uses Git annotated tags as milestones so progress is visible
without requiring a GitHub token or CLI. Each tag is pushed with the branch
merge it records.

GitHub does not expose milestone creation through plain `git`; the equivalent
GitHub milestones can be created later from the tag list below.

| Milestone | Phase | Branch | Merge target | Tag |
| --- | --- | --- | --- | --- |
| Foundation | 1.1 | `1-project-setup-...` | `dev` | `milestone-1.1-foundation` (historical) |
| Frontend foundation | 1.2 | `2-frontend-foundation-...` | `dev` | `milestone-1.2-frontend` (historical) |
| Backend foundation | 1.3 | `3-backend-database-foundation-...` | `dev` | `milestone-1.3-backend` (historical) |
| Upload API | 2.2 | `7-upload-api-file-validation-ownership-storage` | `dev` | `milestone-2.2-upload-api` |
| Upload UI | 2.1 | `8-upload-ui-with-drag-and-drop-progress-status` | `dev` | `milestone-2.1-upload-ui` |
| Parsing and processing | 2.3 | `9-parsing-metadata-processing-status-error-handling` | `dev` | `milestone-2.3-parsing` |

## Workflow

1. Implement one branch on its own and run its checks.
2. Commit and push the branch.
3. Merge the branch into `dev` with a merge commit.
4. Tag the merge commit with the milestone tag and push the tag.
5. Start the next branch from the updated `dev`.

`main` stays stable and receives `dev` only at release points.
