{
  description = "Lua and Luau source minifier";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      forSystem = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          package = pkgs.callPackage ./package.nix { lua = pkgs.lua5_4; };
        in
        {
          packages.default = package;
          checks = import ./checks.nix { inherit pkgs package; };
          devShells.default = import ./shell.nix { inherit pkgs; };
        };
    in
    {
      packages = forAllSystems (system: (forSystem system).packages);
      checks = forAllSystems (system: (forSystem system).checks);
      devShells = forAllSystems (system: (forSystem system).devShells);
    };
}
