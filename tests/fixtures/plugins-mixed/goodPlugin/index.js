export default {
  name: 'goodPlugin',
  init(app) {
    this.app = app;
  },
  async execute(input) {
    return { status: 'ok', echoed: input };
  },
};
