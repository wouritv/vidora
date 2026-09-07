FROM node:22-alpine

WORKDIR /app

ARG VITE_SUPABASE_URL=http://localhost:3000
ARG VITE_SUPABASE_ANON_KEY=supabase_key
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

COPY package.json package-lock.json* ./

RUN npm install

COPY . .

# Security: run the dev server as the non-root `node` user already present
# in the official node images, rather than root (audit finding H14).
RUN chown -R node:node /app
USER node

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
