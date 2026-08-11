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
      packages = forAll (system: pkgs: {
        emulator86box = pkgs._86box;
      });

      # The 86Box ROM set, exposed for inspection / driver wiring.
      romsPath = roms86box.outPath;
    };
}
