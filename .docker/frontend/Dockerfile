FROM node:18-alpine

WORKDIR /app

COPY frontend .
RUN yarn

RUN yarn build

EXPOSE 5173

CMD ["npm", "run", "dev"]
