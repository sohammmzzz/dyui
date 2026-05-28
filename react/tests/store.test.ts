import { describe, expect, it } from "vitest";

import {
  initialState,
  reducer,
  selectCards,
  selectSurfaces,
} from "../src/store";
import type { DyUIEvent } from "../src/types";

function ev(over: Partial<DyUIEvent>): DyUIEvent {
  return {
    id: "1",
    component: "text",
    props: {},
    status: "done",
    surface: "default",
    ...over,
  };
}

describe("store reducer", () => {
  it("adds a new card in order", () => {
    let s = reducer(initialState, { kind: "ui", event: ev({ id: "a" }) });
    s = reducer(s, { kind: "ui", event: ev({ id: "b" }) });
    expect(s.order).toEqual(["a", "b"]);
    expect(selectCards(s).map((c) => c.id)).toEqual(["a", "b"]);
  });

  it("updates an existing card in place (pending -> done)", () => {
    let s = reducer(initialState, {
      kind: "ui",
      event: ev({ id: "x", status: "pending" }),
    });
    s = reducer(s, {
      kind: "ui",
      event: ev({ id: "x", status: "done", props: { rows: [[1]] } }),
    });
    expect(s.order).toEqual(["x"]); // no duplicate
    expect(s.cards.x.status).toBe("done");
    expect(s.cards.x.props).toEqual({ rows: [[1]] });
  });

  it("merges props when replace is false", () => {
    let s = reducer(initialState, {
      kind: "ui",
      event: ev({ id: "m", props: { a: 1 } }),
    });
    s = reducer(s, {
      kind: "ui",
      event: ev({ id: "m", props: { b: 2 }, replace: false }),
    });
    expect(s.cards.m.props).toEqual({ a: 1, b: 2 });
  });

  it("replaces props by default", () => {
    let s = reducer(initialState, {
      kind: "ui",
      event: ev({ id: "r", props: { a: 1 } }),
    });
    s = reducer(s, { kind: "ui", event: ev({ id: "r", props: { b: 2 } }) });
    expect(s.cards.r.props).toEqual({ b: 2 });
  });

  it("dismiss removes a card", () => {
    let s = reducer(initialState, { kind: "ui", event: ev({ id: "d" }) });
    s = reducer(s, { kind: "dismiss", id: "d" });
    expect(s.order).toEqual([]);
    expect(s.cards.d).toBeUndefined();
  });

  it("groups by surface via selector", () => {
    let s = reducer(initialState, { kind: "ui", event: ev({ id: "1", surface: "left" }) });
    s = reducer(s, { kind: "ui", event: ev({ id: "2", surface: "right" }) });
    expect(selectSurfaces(s).sort()).toEqual(["left", "right"]);
    expect(selectCards(s, "left").map((c) => c.id)).toEqual(["1"]);
  });

  it("accumulates tokens", () => {
    let s = reducer(initialState, { kind: "token", text: "Hel" });
    s = reducer(s, { kind: "token", text: "lo" });
    expect(s.tokens).toBe("Hello");
  });

  it("reset clears everything", () => {
    let s = reducer(initialState, { kind: "ui", event: ev({ id: "z" }) });
    s = reducer(s, { kind: "reset" });
    expect(s).toEqual(initialState);
  });
});
