#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iterator>
#include <type_traits>
#include <unordered_map>
#include <utility>
#include <vector>

namespace morpheus {

template <typename RecordId = std::uint32_t>
class CompressedBitmap {
    static_assert(std::is_unsigned_v<RecordId>, "CompressedBitmap requires an unsigned RecordId");
    static_assert(sizeof(RecordId) <= sizeof(std::uint32_t), "CompressedBitmap currently supports up to 32-bit ids");
public:
    bool add(RecordId id) { const auto [h,l]=split(id); auto& v=containers_[h]; const auto it=std::lower_bound(v.begin(),v.end(),l); if(it!=v.end()&&*it==l)return false; v.insert(it,l); ++size_; return true; }
    bool remove(RecordId id) { const auto [h,l]=split(id); auto b=containers_.find(h); if(b==containers_.end())return false; auto& v=b->second; const auto it=std::lower_bound(v.begin(),v.end(),l); if(it==v.end()||*it!=l)return false; v.erase(it); --size_; if(v.empty())containers_.erase(b); return true; }
    [[nodiscard]] bool contains(RecordId id) const noexcept { const auto [h,l]=split(id); const auto b=containers_.find(h); return b!=containers_.end()&&std::binary_search(b->second.begin(),b->second.end(),l); }
    [[nodiscard]] std::size_t size() const noexcept{return size_;}
    [[nodiscard]] bool empty() const noexcept{return size_==0;}
    [[nodiscard]] std::size_t container_count() const noexcept{return containers_.size();}
    [[nodiscard]] std::vector<RecordId> values() const { std::vector<std::pair<std::uint16_t,const std::vector<std::uint16_t>*>> ordered; ordered.reserve(containers_.size()); for(const auto& [h,l]:containers_)ordered.emplace_back(h,&l); std::sort(ordered.begin(),ordered.end(),[](const auto&a,const auto&b){return a.first<b.first;}); std::vector<RecordId> out; out.reserve(size_); for(const auto&[h,lows]:ordered)for(const auto l:*lows)out.push_back(join(h,l)); return out; }
    [[nodiscard]] CompressedBitmap intersection(const CompressedBitmap& other) const { CompressedBitmap out; for(const auto&[h,left]:containers_){const auto r=other.containers_.find(h); if(r==other.containers_.end())continue; std::vector<std::uint16_t> merged; merged.reserve(std::min(left.size(),r->second.size())); std::set_intersection(left.begin(),left.end(),r->second.begin(),r->second.end(),std::back_inserter(merged)); if(!merged.empty()){out.size_+=merged.size(); out.containers_.emplace(h,std::move(merged));}} return out; }
    [[nodiscard]] CompressedBitmap set_union(const CompressedBitmap& other) const {
        CompressedBitmap out;
        out.containers_.reserve(containers_.size() + other.containers_.size());
        for (const auto& [h, left] : containers_) {
            const auto r = other.containers_.find(h);
            if (r == other.containers_.end()) {
                out.size_ += left.size();
                out.containers_.emplace(h, left);
                continue;
            }
            std::vector<std::uint16_t> merged;
            merged.reserve(left.size() + r->second.size());
            std::set_union(left.begin(), left.end(), r->second.begin(), r->second.end(), std::back_inserter(merged));
            out.size_ += merged.size();
            out.containers_.emplace(h, std::move(merged));
        }
        for (const auto& [h, right] : other.containers_) {
            if (containers_.find(h) != containers_.end()) continue;
            out.size_ += right.size();
            out.containers_.emplace(h, right);
        }
        return out;
    }
private:
    std::unordered_map<std::uint16_t,std::vector<std::uint16_t>> containers_; std::size_t size_=0;
    static constexpr std::pair<std::uint16_t,std::uint16_t> split(RecordId id) noexcept {const auto v=static_cast<std::uint32_t>(id); return {static_cast<std::uint16_t>(v>>16U),static_cast<std::uint16_t>(v&0xFFFFU)};}
    static constexpr RecordId join(std::uint16_t h,std::uint16_t l) noexcept{return static_cast<RecordId>((static_cast<std::uint32_t>(h)<<16U)|l);}
};

template <typename Category, typename RecordId = std::uint32_t>
class CompressedBitmapFilterIndex {
public:
    bool add(const Category& c,RecordId id){return postings_[c].add(id);}
    bool remove(const Category& c,RecordId id){auto it=postings_.find(c); if(it==postings_.end()||!it->second.remove(id))return false; if(it->second.empty())postings_.erase(it); return true;}
    [[nodiscard]] bool contains(const Category& c,RecordId id) const noexcept{const auto it=postings_.find(c); return it!=postings_.end()&&it->second.contains(id);}
    [[nodiscard]] std::vector<RecordId> filter(const Category& c) const{const auto it=postings_.find(c); return it==postings_.end()?std::vector<RecordId>{}:it->second.values();}
    [[nodiscard]] std::vector<RecordId> filter_all(const Category&a,const Category&b) const{const auto l=postings_.find(a),r=postings_.find(b); if(l==postings_.end()||r==postings_.end())return {}; return l->second.intersection(r->second).values();}
private: std::unordered_map<Category,CompressedBitmap<RecordId>> postings_;
};

} // namespace morpheus