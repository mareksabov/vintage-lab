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
      packages = forAll (system: pkgs: rec {
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

        vintage = pkgs.symlinkJoin {
          name = "vintage";
          paths = [ vintage-unwrapped ];
          nativeBuildInputs = [ pkgs.makeWrapper ];
          postBuild = ''
            wrapProgram $out/bin/vintage \
              --set VINTAGE_86BOX_BIN ${emulator86box}/bin/86Box \
              --set VINTAGE_ROMS_86BOX ${roms86box} \
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
