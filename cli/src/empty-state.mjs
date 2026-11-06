// Empty values describe actual recorded data, never projected or sample usage.
export const EMPTY = Object.freeze({
  threads: ['Threads 0 | spent 0 | saved 0', 'First action: run tervory chat and send a message.'],
  receipts: ['Receipts 0 | cost — | baseline — | saved —', 'First action: send a message in tervory chat to record a receipt.'],
  messages: ['Messages 0 | steps 0', 'First action: enter a message at >.'],
  sessions: ['Code sessions 0', 'First action: run tervory code and enter a task.'],
  code: ['Messages 0 | tool steps 0', 'First action: enter a task at >.'],
  models: ['Models 0 | in —/M | out —/M', 'First action: ask your administrator to configure a permitted Tank model.'],
  tools: ['Tool steps 0', 'First action: enter a task that reads or changes your project.'],
  files: ['Files 0', 'First action: add a file in this project folder.'],
  matches: ['Matches 0', 'First action: search for text present in a project file.'],
  branches: ['Branches 0', 'First action: stage a project file, then use /commit.'],
  staged: ['Staged files 0', 'First action: stage the project files you want to commit.'],
});

export function emptyState(name) { return EMPTY[name].join('\n') + '\n'; }
