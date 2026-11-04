# ApKit4D

An application for visualizing and analyzing 4D (3D space + time) microscopy recordings of swimming algae taken in the Zeiss [`.czi`](https://www.zeiss.com/microscopy/en/products/software/zeiss-zen/czi-image-file-format.html) format. The microorganisms are detected in 3D, their trajectories tracked across frames in order to perform a motility analysis and to extract metrics.

## How we work

- `main` is protected: nobody can push to it, every change goes through a pull request.
- Branches are short-lived (less than a day) and pull requests are small (less than 200 lines).
- A pull request needs the approval of a teammate and a green CI, and must be up to date with
  `main`. It is merged with a squash merge.
- The backlog and the sprints are on the Jira board of the team, not in this repository.
- The title of a pull request starts with the key of the Jira issue it implements:
  `ABC-12 Add the login form`.
- If `main` is red, fixing it comes before anything else.

## CI

`.github/workflows/ci.yml` runs on every pull request. It starts empty and always passes: add
the steps that build and test the project as soon as there is something to test.
