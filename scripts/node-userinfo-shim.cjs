// Node 24 may fail to resolve Windows accounts whose profile contains non-ASCII characters.
// tsx only needs the username to choose a temporary directory, so provide a safe fallback.
const os = require('node:os')

try {
  os.userInfo()
} catch {
  os.userInfo = () => ({
    gid: -1,
    homedir: process.env.USERPROFILE || process.cwd(),
    shell: null,
    uid: -1,
    username: process.env.USERNAME || 'star-nutri',
  })
}
