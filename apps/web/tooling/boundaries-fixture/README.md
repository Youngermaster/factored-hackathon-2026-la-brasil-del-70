# Boundary rule fixture

A minimal `src/` tree that mirrors the web app layers. `tooling/boundaries.test.ts` lints import statements as if they were written inside these folders and asserts that the policies in `eslint.boundaries.js` accept or reject them. The files only exist to be import targets; the main ESLint run ignores this directory.
