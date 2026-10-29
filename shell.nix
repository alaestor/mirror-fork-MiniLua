{ pkgs }:

pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (ps: with ps; [ click colorama pytest setuptools ]))
    pkgs.lua5_4
    pkgs.luau
  ];
}
