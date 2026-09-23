# Repository Guidelines

## Project Structure & Module Organization

This repository currently has no application source, tests, assets, or package manifest. Keep the root focused on project documentation and configuration. When implementation begins, group production code by feature under `src/`, put automated tests under `tests/` (or beside the code if the chosen framework favors that), and keep static assets under `assets/`. Update this guide when the actual layout is established.

## Build, Test, and Development Commands

No build, test, or local run commands are configured yet. Before adding code, choose a toolchain and document its exact setup, run, build, and test commands in `README.md`. Prefer commands that work from the repository root and can also run in CI. Do not assume a dependency manager or runtime until its manifest is committed.

## Coding Style & Naming Conventions

Follow the formatter and linter configured for the language introduced to the project; commit their configuration with the first source files. Use descriptive names and keep one consistent indentation style within each language. Name files after their feature or module, and use the language's usual conventions for functions, types, and constants. Avoid unrelated formatting changes in focused patches.

## Testing Guidelines

There is no test framework or coverage target yet. Add tests with new behavior and bug fixes once a framework is selected. Give test files names that clearly match the code they exercise, such as `tests/auth.test.ts` for `src/auth.ts`. Document the test command and any coverage threshold when CI is introduced.

## Commit & Pull Request Guidelines

No commit history is available here, so there is no established message convention. Use short, imperative commit subjects that describe the change, such as `Add authentication tests`. Keep pull requests focused; include a summary, the commands used to verify the change, and any related issue. Include screenshots when a change affects the user interface.

## Security & Configuration

Do not commit credentials, tokens, or local environment files. Add an example configuration file with safe placeholder values when configuration is needed, and document required variables in `README.md`.
