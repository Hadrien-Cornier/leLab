# Camera rotation verification

Date: October 4, 2026 (local time). Repository: huggingface/leLab.

Source: c07927486591e02be83d4a225167613bb41f5f5c.
Baseline: 454b19fabe6b4e4fbff69025944fb57e410daba7.

## Result

LeLab exposes per-camera clockwise rotation at 0, 90, 180, and 270 degrees.
The profile and API dimensions describe native capture. Quarter turns swap output dimensions.
Pinned LeRobot v0.6.0 receives output dimensions and maps 270 to its -90 enum.
Only raw browser previews use CSS rotation. Saved and streamed backend frames receive no second rotation.

## Reproduction

`reproduce_recording.py` exercises the public POST /start-recording route with an upside-down asymmetric source.
It supplies the robot producer, but uses the actual camera configuration, image processing, dataset writer, finalization, and MP4 decode.
Unchanged upstream ignores rotation 180. The decoded video has a mean absolute error of 101.49 against the upright reference.
The fix produces rotation 180 and a decoded mean error of 2.5. See before.log and after.log.
This establishes a missing capability, rather than an advertised-feature regression.

`workflow.py` extends the check through the actual record_with_web_events and pinned record_loop.
It replaces hardware factories and cv2.VideoCapture with supplied motor and capture devices.
The real camera connection, read thread, image processing, observation loop, writer, finalization, and video decode execute.
Each of four sessions saves five frames from two cameras. Front rotation stays zero. Wrist rotation covers all four choices.
All native capture requests remain 96 by 64. Quarter turns produce 64 by 96 output.
Exact live observations agree with the marked reference. Decoded wrist videos have mean absolute error 2.75 to 2.96.
The allowed decoded error is below 10 on the 0-to-255 pixel scale because AV1 encoding is lossy.
Actual rollout camera arguments parse into OpenCVCameraConfig and produce the expected camera input exactly.
No policy model or rollout subprocess executes. See workflow.log.

The two workflow-harness logs preserve harness failures: a mock did not support an isinstance check, and a spawn guard was missing.
The corrected harness completes all four sessions. These failures do not describe production defects.

## Browser check

`browser.mjs` operates the built production UI on localhost port 8088.
It supplies getUserMedia from a labeled asymmetric canvas. It intercepts all API requests with a separate in-memory profile.
It checks all four controls, complete-frame bounds, saved rotation, profile reload, and browser errors.
All checks pass. There are no page errors. The 180 and 90 screenshots show the actual rendered controls and frame.
No physical camera or live backend endpoint is used.

## Required checks

- Python suite: 293 passed, 7 warnings. See pytest.log.
- Node.js 22 frontend suite: 34 tests in 8 files passed. See frontend-tests.log.
- Complete pre-commit suite: all hooks passed. See precommit-final.log.
- Node.js 22 production build passed. The repeated build produces an identical staged bundle. See frontend-build logs and empty bundle-freshness.log.
- Changed frontend source and tests: ESLint has zero errors and two existing Landing.tsx hook warnings. See eslint.log.
- Full TypeScript check: five errors, identical to a fresh source copy of unchanged origin/main. See typescript-current.log and typescript-baseline.log.
- Independent review identified invalid-profile error handling and recording-preview cropping. Both are corrected. Re-review reports no remaining blockers.
- Whitespace and complete diff review passed. Generated bundles include the hydrated upstream Git LFS assets.

Python warnings include existing FastAPI deprecations, a missing local pytest-asyncio option, and a test-only socket accept thread abort.
The TypeScript errors occur in unchanged useOnboardingProgress.ts and meshLoaders.ts.

## Repeat the checks

Install LeLab test dependencies and the pinned LeRobot dependency.
Set PYTHONPATH to the checkout that you want to test before executing either Python script.
For the baseline, execute reproduce_recording.py against baseline source. Then execute it against the fix.
Execute workflow.py against the fix. Both scripts use new temporary dataset directories.
On this macOS run, FFmpeg 8 libraries require DYLD_LIBRARY_PATH=/opt/homebrew/opt/ffmpeg@8/lib.

For the browser check, install Playwright and its Chromium browser. Start npm run preview on port 8088.
Execute node browser.mjs. LELAB_UI_URL selects another UI URL.
PLAYWRIGHT_MODULE and CHROMIUM_EXECUTABLE can select an existing local Playwright runtime and browser.
Use Node.js 22 for npm ci, npm test, and npm run build. Commit the generated frontend/dist bundle.

## Limits and review focus

Physical USB camera modes and the physical SO-101 remain unverified. No learned policy performance is measured.
The highest-value hardware check is a new rectangular scene across setup preview, saved MP4, and inference observation.
Use the same rotation as the training data. Dimensions cannot distinguish 0 from 180 degrees.
Existing recordings and checkpoints do not change. Camera identity and backend preview changes from issue 119 stay outside this PR.
