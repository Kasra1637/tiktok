# Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Install with yarn, not npm

```bash
yarn install
```

`yarn.lock` is the tracked lockfile and the Docker image builds with
`yarn install --frozen-lockfile`. A `preinstall` guard
(`scripts/require-yarn.js`) rejects npm, because:

- `npm install` fails peer resolution outright (`ERESOLVE`, React 19 vs
  `@clerk/clerk-react`), and
- `npm install --legacy-peer-deps` *appears* to succeed but hoists
  `ajv-keywords@5` next to `ajv@6` instead of the `ajv@8` it requires. The
  build then dies with `Cannot find module 'ajv/dist/compile/codegen'`. yarn
  avoids this by nesting `schema-utils@4`'s own `ajv@8` beneath it, leaving the
  top-level `ajv@6` for eslint and fork-ts-checker.

Set `ALLOW_NPM_INSTALL=true` to bypass the guard.

Scripts run through craco, not plain CRA (`yarn start`, `yarn build`,
`yarn test` invoke `craco start` / `craco build` / `craco test`). Two extra
project scripts exist:

```bash
yarn check:imports   # every named import resolves
yarn check:logic      # pure frontend helpers behave (video lengths, intents,
                      # profile selection) — evaluated from the shipped files
yarn check            # both of the above
```

## Environment

CRA inlines `process.env.REACT_APP_*` at **build** time, so these must be set
when the bundle is built, not at runtime:

```bash
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_CLERK_PUBLISHABLE_KEY=pk_...   # optional; unset means anonymous access
```

## Available Scripts

In the project directory, you can run:

### `yarn start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `yarn test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `yarn build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `eject`

Not available. This project builds through craco rather than raw react-scripts,
so there is nothing to eject from; customize via `craco.config.js` instead.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)
