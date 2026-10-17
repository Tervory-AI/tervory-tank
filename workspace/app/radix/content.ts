// Demonstration content only. Never merge examples into tenant scan results.
export const checks = [
  { title: "Secrets", copy: "Find exposed credentials. Report the location, never the value." },
  { title: "Dependencies", copy: "Compare package versions with advisory data included with Radix." },
  { title: "Unsafe code", copy: "Look for risky patterns in the code supplied for review." },
] as const;

export const exampleFindings = [
  {
    id: "example-secret",
    severity: "Critical",
    title: "Exposed credential",
    file: "config/settings.py",
    line: 12,
    rule: "Example secret rule",
    fix: "Remove the credential, rotate it, and review the repository history.",
    detail: "Keep credentials in the server environment. Check that old credentials no longer work. The report records the location, never the secret value.",
  },
  {
    id: "example-dependency",
    severity: "High",
    title: "Risky dependency",
    file: "requirements.txt",
    line: 8,
    rule: "Example dependency advisory",
    fix: "Move to a patched package version and check compatibility.",
    detail: "Review the advisory and the package release notes, update the dependency, and run the project tests before checking again.",
  },
  {
    id: "example-static",
    severity: "Medium",
    title: "Unsafe SQL query",
    file: "app/search.py",
    line: 24,
    rule: "Example SQL rule",
    fix: "Use a parameterised query instead of joining user input into SQL.",
    detail: "Pass user values separately from the query text. Add a test for unexpected input, then run a fresh code check.",
  },
] as const;

export const sourceSections = [
  {
    id: "keys", label: "API keys",
    description: "No API keys are needed for offline code checks.",
    title: "Keys cannot be added from this page.",
    copy: "No credentials are requested or stored.",
    example: "Saved key",
  },
  {
    id: "files", label: "Files",
    description: "Code archives supplied for an offline check.",
    title: "Uploads are not connected yet.",
    copy: "The scan service accepts ZIP, tar.gz, or git bundle archives. This page cannot upload them yet.",
    empty: "No file list is connected.",
  },
  {
    id: "links", label: "Source links",
    description: "Reference links for a security review.",
    title: "No client hostname has been approved here.",
    copy: "Links cannot be added or fetched from this page. Outbound access stays disabled.",
    empty: "No links are connected.",
  },
  {
    id: "mcp", label: "MCP connections",
    description: "Connections to external tools.",
    title: "External connections are disabled.",
    copy: "No server is contacted and no token is requested.",
    example: "Saved token",
  },
] as const;

export function exampleReport(): string {
  return [
    "# Radix — EXAMPLE report",
    "",
    "EXAMPLE ONLY. These findings are made up. This is not a scan of your code.",
    "Outbound scans remain disabled. This report does not approve a release.",
    "",
    ...exampleFindings.flatMap((finding) => [
      "## " + finding.severity + " — " + finding.title + " (Example)",
      finding.file + ":" + finding.line,
      "Rule: " + finding.rule,
      finding.fix,
      finding.detail,
      "",
    ]),
  ].join("\n");
}
