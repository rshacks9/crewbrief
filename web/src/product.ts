// Business settings for the landing page. Edit here; nothing else needs to change.
// Prices are the owner's call. These are the proposed launch prices.

const EARLY_ACCESS_EMAIL = "Tgaffneyiii@proton.me";
const EARLY_ACCESS_BODY = [
  "Hi, I'd like early access to CrewBrief.",
  "",
  "Airline name:",
  "vAMSYS airline link:",
  "Roughly how many routes:",
  "Main aircraft types:",
  "",
].join("\n");

export const PRODUCT = {
  name: "CrewBrief",
  /** Where "Get early access" goes: a form, a Discord invite or a mailto: link. null hides the button. */
  earlyAccessUrl: `mailto:${EARLY_ACCESS_EMAIL}?subject=${encodeURIComponent("CrewBrief early access")}&body=${encodeURIComponent(EARLY_ACCESS_BODY)}` as string | null,
  plans: [
    {
      name: "Founding airline",
      price: 9,
      badge: "First 10 airlines",
      featured: true,
      points: ["Everything in Standard", "Price locked while you stay subscribed", "Direct line to request features"],
    },
    {
      name: "Standard",
      price: 15,
      badge: null,
      featured: false,
      points: ["Up to 300 routes", "Live weather and runway winds", "Fuel and approach cards", "Your colours and logo", "Embed on your own site"],
    },
    {
      name: "Large network",
      price: 29,
      badge: null,
      featured: false,
      points: ["Unlimited routes", "Custom fuel figures per type", "Priority support"],
    },
  ],
} as const;
