class Demo {
  get value() { return this._v }
  set value(x) { this._v = x }
  static ping() { return "pong" }
}
const obj = {
  get foo() { return 1 },
  set foo(v) { this._f = v },
  bar() { return 2 } // regular method (no type)
}
