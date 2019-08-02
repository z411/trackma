#!/bin/bash

flatpak-builder flatpak-builder io.github.TrackmaGtk.json --user --force-clean --repo=./repo --jobs=1
flatpak build-bundle ./repo trackma-gtk.flatpak io.github.TrackmaGtk

if [ -f trackma-gtk.flatpak ]; then
	echo "Install trackma-gtk.flatpak"
else
	echo "Something went wrong, unable to find Flatpak file"
fi
