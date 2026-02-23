# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)


# Push your branch with these files:
# docs.yml
# requirements.txt
# docs updates
# In GitHub repo:
# Settings → Pages
# Under Build and deployment, set Source to GitHub Actions
# Save
# Merge/push to main (workflow is configured for main pushes), or run manually:
# Actions → Docs → Run workflow
# Wait for both jobs in Docs workflow:
# build
# deploy
# Open deployed site:
# https://<your-username>.github.io/<repo-name>/
# Or use the URL shown in the deploy job output (page_url).
# If you want it to deploy from every branch push, I can adjust docs.yml trigger from main to *.
