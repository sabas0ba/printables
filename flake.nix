{
  description = "Pinned toolchain for printables";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/597283ad8aa0b331c788e97c4c262d58877074ef";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forEachSystem = f: nixpkgs.lib.genAttrs systems
        (system: f (import nixpkgs { inherit system; }));
    in {
      devShells = forEachSystem (pkgs: {
        default = pkgs.mkShell {
          packages = [
            pkgs.python312
            pkgs.uv
            pkgs.libGL
            pkgs.libx11
            pkgs.libxext
            pkgs.libxrender
            pkgs.libxi
            pkgs.libsm
            pkgs.libice
            pkgs.fontconfig
            pkgs.freetype
          ];
          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
            pkgs.libGL
            pkgs.libx11
            pkgs.libxext
            pkgs.libxrender
            pkgs.libxi
            pkgs.libsm
            pkgs.libice
            pkgs.fontconfig
            pkgs.freetype
            pkgs.stdenv.cc.cc.lib
          ];
        };
      });
    };
}
