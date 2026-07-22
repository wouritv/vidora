FROM node:20-alpine

WORKDIR /app

ARG VITE_SUPABASE_URL=http://localhost:3000
ARG VITE_SUPABASE_ANON_KEY=supabase_key
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

COPY package.json package-lock.json* ./

RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
