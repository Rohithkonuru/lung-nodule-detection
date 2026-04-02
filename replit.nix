{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.glib
    pkgs.libGL
    pkgs.postgresql
    pkgs.wget
    pkgs.nodejs
  ];
}
