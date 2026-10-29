{ pkgs, package }:

{
  package = package;
  lua51 = package.override { lua = pkgs.lua5_1; };
  lua52 = package.override { lua = pkgs.lua5_2; };
  lua53 = package.override { lua = pkgs.lua5_3; };
}
