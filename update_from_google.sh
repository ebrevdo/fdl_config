# Rebase based on the google repo's main branch,
# manually pointing to git@github.com:google/fiddle.git
# as the remote.

set -e

# If google is not already one of the remotes, add it.
if ! git remote | grep -q google; then
    git remote add google git@github.com:google/fiddle.git
fi
git pull --rebase google main


