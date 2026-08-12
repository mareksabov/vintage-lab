{
  description = "Reproducible retro machine launcher";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    roms86box = {
      url = "github:86Box/roms";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, roms86box }:
    let
      systems = [ "aarch64-darwin" "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f system nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAll (system: pkgs:
        let
          # VICE has no usable nixpkgs build on Darwin (Linux-only deps: alsa,
          # pulseaudio, libevdev; GTK3 also fails to build there). Use the
          # official prebuilt native arm64 SDL2 app from the VICE project. Its
          # binaries are code-signed, so we copy the distribution verbatim and
          # never strip/patch it (dontFixup), keeping the signatures valid.
          vice-macos = pkgs.stdenvNoCC.mkDerivation {
            pname = "vice-macos-bin";
            version = "3.9";
            src = pkgs.fetchurl {
              url = "https://downloads.sourceforge.net/project/vice-emu/releases/binaries/macosx/vice-arm64-sdl2-3.9.dmg";
              hash = "sha256-ZYQRF8uUVnxolo3B/ZmjqfZXfzaPNZ6LG2p72FH1imU=";
            };
            nativeBuildInputs = [ pkgs.undmg ];
            sourceRoot = ".";
            dontFixup = true;
            installPhase = ''
              runHook preInstall
              mkdir -p "$out"
              # undmg extracts the distribution folder alongside an
              # `Applications` symlink; glob its name (no trailing slash, so it
              # is copied AS $out/vice) so a version bump only needs the
              # url+hash changed, not this path.
              cp -R vice-*-sdl2-* "$out/vice"
              runHook postInstall
            '';
            meta = {
              description = "Official VICE arm64 SDL2 macOS build (Commodore emulators)";
              homepage = "https://vice-emu.sourceforge.io/";
              license = nixpkgs.lib.licenses.gpl2Plus;
              platforms = [ "aarch64-darwin" ];
            };
          };

          # Directory holding the VICE binaries (x64sc, xvic, ...) per platform:
          # nixpkgs on Linux, the prebuilt app on aarch64-darwin, nothing
          # elsewhere. The driver joins the per-model binary name onto this dir.
          viceBinDir =
            if pkgs.stdenv.isLinux then "${pkgs.vice}/bin"
            else if system == "aarch64-darwin" then "${vice-macos}/vice/bin"
            else null;
        in
        rec {
        emulator86box = pkgs._86box;

        vintage-unwrapped = pkgs.python3Packages.buildPythonApplication {
          pname = "vintage";
          version = "0.1.0";
          src = ./.;
          pyproject = true;
          build-system = [ pkgs.python3Packages.setuptools ];
          # No runtime Python deps (stdlib only).
          doCheck = false;
        };

        vintage =
          let
            # Wire VINTAGE_VICE_BIN_DIR only where the VICE binaries exist (see
            # viceBinDir above). optionalString leaves the reference unforced
            # when null, so unsupported platforms (e.g. x86_64-darwin) still
            # evaluate.
            viceArg = nixpkgs.lib.optionalString (viceBinDir != null)
              "--set VINTAGE_VICE_BIN_DIR ${viceBinDir}";
          in
          pkgs.symlinkJoin {
            name = "vintage";
            paths = [ vintage-unwrapped ];
            nativeBuildInputs = [ pkgs.makeWrapper ];
            postBuild = ''
              wrapProgram $out/bin/vintage \
                --set VINTAGE_86BOX_BIN ${emulator86box}/bin/86Box \
                --set VINTAGE_ROMS_86BOX ${roms86box} \
                ${viceArg} \
                --prefix PATH : ${pkgs.mtools}/bin
            '';
          };

        default = vintage;
      });

      apps = forAll (system: _:
        let program = "${self.packages.${system}.vintage}/bin/vintage";
        in {
          default = { type = "app"; program = program; };
          vintage = { type = "app"; program = program; };
        });

      devShells = forAll (system: pkgs: {
        default = pkgs.mkShell {
          packages = [ pkgs.python311 pkgs.python311Packages.pytest pkgs.mtools ];
          shellHook = ''
            export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
          '';
        };
      });

      # The 86Box ROM set, exposed for inspection / driver wiring.
      # roms86box is a flake=false source-info set; .outPath extracts the Nix store path so `nix build .#romsPath` works.
      romsPath = roms86box.outPath;
    };
}
