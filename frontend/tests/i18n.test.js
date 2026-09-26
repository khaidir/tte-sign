import { describe, it, expect } from "vitest";
import id from "../src/i18n/id.js";

describe("i18n id.js", () => {
    const requiredKeys = [
        "nav.upload",
        "nav.place",
        "nav.download",
        "upload.title",
        "upload.desc",
        "verify.title",
        "verify.desc",
        "footer.ttl",
    ];

    for (const key of requiredKeys) {
        it(`has key "${key}"`, () => {
            expect(id).toHaveProperty(key);
            expect(typeof id[key]).toBe("string");
        });
    }

    it("has all required keys", () => {
        for (const key of requiredKeys) {
            expect(id).toHaveProperty(key);
        }
    });
});
