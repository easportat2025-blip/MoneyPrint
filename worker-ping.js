export default {
  async scheduled(event, env, ctx) {
    const route = {
      "0 16 * * *": "short-acc1",
      "0 19 * * *": "short-acc1",
      "0 22 * * *": "short-acc1",
      "30 17 * * *": "short-acc2",
      "30 20 * * *": "short-acc2",
      "30 23 * * *": "short-acc2",
      "0 15 */5 * *": "long-video",
    }[event.cron];
    if (!route) return;
    const res = await fetch(
      `https://api.github.com/repos/${env.GH_REPO}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `token ${env.GH_TOKEN}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json",
          "User-Agent": "moneyprint-ping",
        },
        body: JSON.stringify({ event_type: route }),
      }
    );
    console.log(route, res.status);
  },
};
