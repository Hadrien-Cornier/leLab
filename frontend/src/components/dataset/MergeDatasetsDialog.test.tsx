// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, test } from "vitest";

import MergeDatasetsDialog from "./MergeDatasetsDialog";

test("opens with the browsed local dataset retained as the first merge source", async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);

  try {
    await act(async () => {
      root.render(
        <MergeDatasetsDialog
          datasets={[
            { repo_id: "local/browsed", source: "local" },
            { repo_id: "local/additional", source: "local" },
          ]}
          selectedRepoId="local/browsed"
          open
          onOpenChange={() => {}}
          onMerge={async () => {}}
        />,
      );
    });

    expect(document.body.textContent).toContain("local/browsed is included");
    expect(document.body.textContent).toContain("local/additional");
    expect(document.body.textContent).toContain("Select at least one additional dataset.");
    const mergeButton = [...document.body.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("Merge datasets"),
    ) as HTMLButtonElement;
    expect(mergeButton.disabled).toBe(true);
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});
