# Arch Linux package

This directory contains the Arch `PKGBUILD` for the `why-git` package. It is
an AUR-style VCS package: `makepkg` checks out the latest commit from GitHub,
builds a wheel, and installs it through the normal Arch package mechanism.

Build and install locally:

```bash
cd packaging/arch
makepkg -si
```

Alternatively, use paru directly:

```bash
paru -Bi .
```

After installation, enable the integration for the current shell:

```bash
eval "$(why init bash)"  # Bash
eval "$(why init zsh)"   # zsh
```

For a user-facing stable package, publish a version tag such as `v0.1.0a1`
and create a release-based AUR package named `why-shell`. The current `why-git`
package is useful while the project is still evolving.

`pacman -S` installs packages from configured binary repositories. `paru` can
build this PKGBUILD locally and then install the resulting package with pacman:

```bash
paru -Bi .
```

After this package is published to the AUR, install it with:

```bash
paru -S why-git
```

An official or custom binary repository can be added later if one-command
`pacman -S why-shell` installation is desired.
