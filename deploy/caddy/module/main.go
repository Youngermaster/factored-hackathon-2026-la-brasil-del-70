// Caddy's standard distribution (the same main package as the official build), compiled in apps/web/Dockerfile with
// a current Go toolchain and the dependency versions pinned in go.mod and go.sum. The official 2.11.4 binary carries
// Go standard library and golang.org/x module versions with known, fixed vulnerabilities (deploy/README.md, "Supply
// chain"); rebuilding from this module is how the web image picks up the fixes. To update: change the versions with
// `go get` in a golang container, `go mod tidy`, rebuild the web image, and run `make scan-images`.
package main

import (
	caddycmd "github.com/caddyserver/caddy/v2/cmd"

	_ "github.com/caddyserver/caddy/v2/modules/standard"
)

func main() {
	caddycmd.Main()
}
