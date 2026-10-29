{ lib, python3Packages, lua, luau }:

python3Packages.buildPythonApplication {
  pname = "minilua";
  version = "1.1.0";
  pyproject = true;

  src = lib.cleanSource ./.;
  build-system = [ python3Packages.setuptools ];
  dependencies = with python3Packages; [ click colorama ];

  nativeCheckInputs = [ python3Packages.pytestCheckHook lua luau ];
  pythonImportsCheck = [ "lua_minifier" ];

  meta = {
    description = "Lua and Luau source minifier";
    license = lib.licenses.mit;
    mainProgram = "minilua";
  };
}
